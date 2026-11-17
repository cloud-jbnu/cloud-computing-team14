import handler
from fakes import FakeTable


def raw(id, **over):
    item = {
        "id": id, "category": "contest", "subtype": "해커톤", "source": "주최",
        "title": f"{id} 글의 제목을 충분히 길게 씁니다", "fields": ["ai", "없는분야"],
        "date": "2026-11-17", "url": f"https://example.com/{id}",
    }
    item.update(over)
    return item


def tables():
    return FakeTable(name="items"), FakeTable(name="seen", key_name="seenKey")


def test_validate_drops_bad_items():
    items, invalid = handler.validate([
        raw("a-1"),
        raw("a-2", date="2026/11/17"),
        raw("a-3", category="etc"),
        raw("a-4", title=" "),
        "딕셔너리 아님",
        raw("a-5", repo={"lang": "Go", "starsToday": "많음"}),
    ])
    assert [it["id"] for it in items] == ["a-1"]
    assert invalid == 5
    assert items[0]["fields"] == ["ai"]   # 정해진 값이 아닌 분야는 뺌


def test_find_new_counts_each_stage():
    items_table, seen_table = tables()
    items_table.put_item(Item={"id": "jbnu-1"})
    new_items, stats = handler.find_new([
        raw("jbnu-1"),                                    # 이미 저장됨
        raw("jbnu-2"),
        raw("jbnu-2"),                                    # 실행 내 중복
        raw("devevent-x", title="겨울 오픈소스 해커톤 참가자 모집"),
        raw("cbnu-7", title="[행사] 겨울 오픈소스 해커톤 참가자 모집"),   # 사이트 간 중복
        raw("cbnu-8", date="어제"),                        # 형식 오류
    ], items_table, seen_table)
    assert [it["id"] for it in new_items] == ["jbnu-2", "devevent-x"]
    assert stats == {"collected": 6, "invalid": 1, "dupInRun": 1, "existing": 1, "dupCrossSite": 1, "new": 2}


def test_find_new_without_tables():
    new_items, stats = handler.find_new([raw("jbnu-1"), raw("jbnu-1")])
    assert len(new_items) == 1 and stats["existing"] == 0


def test_second_run_finds_nothing_new():
    """저장하고 나서 같은 글을 다시 수집하면 새 글이 없어야 합니다."""
    items_table, seen_table = tables()
    collected = [raw("jbnu-1"), raw("devevent-x", title="겨울 오픈소스 해커톤 참가자 모집")]

    new_items, _ = handler.find_new(collected, items_table, seen_table)
    saved = handler.save(new_items, items_table)
    handler.dedupe.record(seen_table, saved)
    assert len(saved) == 2

    late = raw("cbnu-7", title="겨울 오픈소스 해커톤 참가자 모집")   # 다른 사이트가 나중에 올린 같은 글
    again, stats = handler.find_new(collected + [late], items_table, seen_table)
    assert again == []
    assert stats["existing"] == 2 and stats["dupCrossSite"] == 1


def test_save_skips_item_saved_meanwhile():
    items_table, _ = tables()
    items, _ = handler.validate([raw("jbnu-1"), raw("jbnu-2")])
    items_table.put_item(Item={"id": "jbnu-1", "title": "먼저 저장된 글"})
    saved = handler.save(items, items_table)
    assert [it["id"] for it in saved] == ["jbnu-2"]
    assert items_table.rows["jbnu-1"]["title"] == "먼저 저장된 글"   # 덮어쓰지 않음
