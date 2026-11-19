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


# ── 상한 · 본문 · 요약 ────────────────────────────────────────
def test_cap_keeps_newest_and_defers_the_rest():
    raws = [raw(f"jbnu-{i}", date=f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}") for i in range(40)]   # 뒤로 갈수록 최신
    items, _ = handler.validate(raws)
    kept, deferred = handler.cap(items)
    assert len(kept) == handler.MAX_NEW_PER_RUN == 30 and deferred == 10
    assert kept[0]["id"] == "jbnu-39"   # 가장 최신 글부터
    assert {it["id"] for it in kept} == {f"jbnu-{i}" for i in range(10, 40)}


def test_cap_under_limit_changes_nothing_but_order():
    items, _ = handler.validate([raw("a-1", date="2026-11-01"), raw("a-2", date="2026-11-03"), raw("a-3", date="2026-11-03")])
    kept, deferred = handler.cap(items)
    assert [it["id"] for it in kept] == ["a-2", "a-3", "a-1"] and deferred == 0


def test_deferred_items_come_back_as_new_next_run():
    """미룬 글은 저장하지 않으므로 다음 실행에서 다시 새 글로 잡혀야 합니다."""
    items_table, seen_table = tables()
    raws = [raw(f"jbnu-{i}", date=f"2026-11-{i + 1:02d}") for i in range(5)]

    new_items, _ = handler.find_new(raws, items_table, seen_table)
    first, deferred = handler.cap(new_items, limit=3)
    handler.dedupe.record(seen_table, handler.save(first, items_table))
    assert deferred == 2

    again, _ = handler.find_new(raws, items_table, seen_table)
    assert {it["id"] for it in again} == {"jbnu-0", "jbnu-1"}


class FakeSource:
    def __init__(self, bodies=None, fail=False):
        self.bodies, self.fail, self.asked = bodies or {}, fail, []

    def fetch_body(self, item):
        self.asked.append(item["id"])
        if self.fail:
            raise RuntimeError("사이트 응답 없음")
        return self.bodies.get(item["id"], "")


class ListOnlySource:
    """fetch_body가 없는 수집기 (목록에 내용이 다 있는 사이트)."""


def test_load_bodies_combines_list_body_and_detail_page():
    source = FakeSource({"a-1": "본문 페이지 내용"})
    raws = [
        raw("a-1", body="목록에서 얻은 내용", _module=source),
        raw("a-2", body="목록 내용만", _module=ListOnlySource()),
        raw("a-3", _module=source),                     # 본문 페이지가 비어 있음
        raw("a-4", _module=source),                     # 새 글이 아니라서 요청하지 않음
    ]
    items, _ = handler.validate(raws[:3])
    bodies = handler.load_bodies(items, raws, pause=0)
    assert bodies == {"a-1": "목록에서 얻은 내용\n\n본문 페이지 내용", "a-2": "목록 내용만", "a-3": ""}
    assert source.asked == ["a-1", "a-3"]


def test_load_bodies_survives_fetch_failure():
    raws = [raw("a-1", body="목록 내용", _module=FakeSource(fail=True))]
    items, _ = handler.validate(raws)
    assert handler.load_bodies(items, raws, pause=0) == {"a-1": "목록 내용"}


def test_internal_keys_are_not_saved():
    items, _ = handler.validate([raw("a-1", body="본문", _module=ListOnlySource())])
    assert "body" not in items[0] and "_module" not in items[0]


def test_add_summaries_attaches_results(monkeypatch):
    raws = [raw("a-1", body="본문", fields=["cloud"]), raw("a-2")]
    items, _ = handler.validate(raws)
    seen = {}

    def fake_summarize(got_items, bodies):
        seen["bodies"] = bodies
        return {"a-1": {"summary": ["요약 한 줄"], "fields": ["ai"]}}

    monkeypatch.setattr(handler.summarize, "summarize", fake_summarize)
    assert handler.add_summaries(items, raws) == 1
    assert seen["bodies"] == {"a-1": "본문", "a-2": ""}
    assert items[0]["summary"] == ["요약 한 줄"] and items[0]["fields"] == ["ai"]   # 수집기 태그 대신 AI 태그
    assert "summary" not in items[1]


def test_add_summaries_failure_keeps_items(monkeypatch):
    def boom(items, bodies):
        raise RuntimeError("Gemini 장애")

    monkeypatch.setattr(handler.summarize, "summarize", boom)
    items, _ = handler.validate([raw("a-1")])
    assert handler.add_summaries(items, [raw("a-1")]) == 0
    assert items[0]["id"] == "a-1" and "summary" not in items[0]


def test_items_without_key_are_saved_without_summary(monkeypatch):
    """GEMINI_API_KEY가 없으면 요약 없이 저장까지 그대로 진행됩니다."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    items_table, seen_table = tables()
    raws = [raw("a-1")]
    new_items, _ = handler.find_new(raws, items_table, seen_table)
    assert handler.add_summaries(new_items, raws) == 0
    assert [it["id"] for it in handler.save(new_items, items_table)] == ["a-1"]
    assert "summary" not in items_table.rows["a-1"]
