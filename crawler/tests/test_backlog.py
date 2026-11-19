"""처음 수집하는 사이트의 밀린 글은 저장만 하고 알리지 않는지 확인합니다 (backlog.py)."""
import backlog
import handler
from fakes import FakeTable


def raw(id, day):
    return {"id": id, "category": "jobs", "subtype": "신입", "source": f"회사{id}", "title": f"{id} 공고 제목을 충분히 길게",
            "fields": [], "date": f"2026-11-{day:02d}", "url": f"https://example.com/{id}"}


def tables():
    return FakeTable(name="items"), FakeTable(name="seen", key_name="seenKey")


def run(raws, items_table, seen_table, limit=3):
    """lambda_handler와 같은 순서로 한 번 실행하고 (저장한 id, 알릴 id)를 돌려줍니다."""
    new_items, _ = handler.find_new(raws, items_table, seen_table)
    quiet = handler.find_quiet(new_items, seen_table)
    new_items, _ = handler.cap(new_items, limit)
    saved = handler.save(new_items, items_table)
    handler.dedupe.record(seen_table, saved)
    return {it["id"] for it in saved}, {it["id"] for it in handler.to_announce(saved, quiet)}


def test_backlog_stays_quiet_across_runs_and_new_posts_are_announced():
    items_table, seen_table = tables()
    listed = [raw(f"jumpit-{i}", i + 1) for i in range(5)]          # 배포 전부터 있던 공고 5건

    saved, announced = run(listed, items_table, seen_table)          # 첫 실행: 3건 저장, 2건은 다음으로 미룸
    assert len(saved) == 3 and announced == set()
    assert seen_table.rows["source#jumpit"]["backlogIds"] == {f"jumpit-{i}" for i in range(5)}

    fresh = raw("jumpit-9", 20)                                      # 배포 뒤 새로 올라온 공고
    saved, announced = run(listed + [fresh], items_table, seen_table)
    assert saved == {"jumpit-0", "jumpit-1", "jumpit-9"}             # 미룬 밀린 글 2건 + 새 공고
    assert announced == {"jumpit-9"}

    saved, announced = run(listed + [fresh], items_table, seen_table)
    assert saved == set() and announced == set()


def test_site_added_later_starts_quiet():
    items_table, seen_table = tables()
    run([raw("jumpit-1", 1)], items_table, seen_table)

    saved, announced = run([raw("jumpit-1", 1), raw("jumpit-2", 2), raw("geeknews-1", 2)], items_table, seen_table)
    assert saved == {"jumpit-2", "geeknews-1"}
    assert announced == {"jumpit-2"}                                 # 처음 보는 geeknews만 조용히
    assert "source#geeknews" in seen_table.rows


def test_marker_written_meanwhile_is_kept(monkeypatch):
    """확인한 사이에 다른 실행이 먼저 적었으면 덮어쓰지 않고, 이번 글도 조용히 둡니다."""
    _, seen_table = tables()
    seen_table.put_item(Item={"seenKey": "source#jumpit", "site": "jumpit", "backlogIds": {"jumpit-0"}})
    monkeypatch.setattr(backlog.dedupe, "batch_get", lambda *a: [])  # 확인할 때는 아직 없었던 것처럼
    items, _ = handler.validate([raw("jumpit-1", 1)])
    assert backlog.quiet_ids(seen_table, items) == {"jumpit-1"}
    assert seen_table.rows["source#jumpit"]["backlogIds"] == {"jumpit-0"}


def test_no_items_needs_no_lookup():
    _, seen_table = tables()
    assert backlog.quiet_ids(seen_table, []) == set()
    assert seen_table.meta.client.batch_get_calls == []


def test_lookup_failure_announces_nothing(monkeypatch):
    def boom(*a):
        raise RuntimeError("DynamoDB 오류")

    monkeypatch.setattr(backlog.dedupe, "batch_get", boom)
    items, _ = handler.validate([raw("jumpit-1", 1), raw("geeknews-1", 1)])
    assert handler.find_quiet(items, FakeTable(key_name="seenKey")) == {"jumpit-1", "geeknews-1"}
