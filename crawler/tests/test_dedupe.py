import pytest

import dedupe
from fakes import FakeTable


def make(id, title="겨울 오픈소스 해커톤 참가자 모집", url=None, category="contest", source="주최"):
    return {"id": id, "title": title, "url": url or f"https://example.com/{id}", "category": category, "source": source}


# ── 키 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("a, b", [
    ("https://example.com/post/1", "http://www.example.com/post/1/"),
    ("https://example.com/post/1", "https://EXAMPLE.com/post/1#comments"),
    ("https://example.com/post?id=1", "https://example.com/post?id=1&utm_source=kakao&utm_medium=sns&fbclid=abc"),
    ("https://example.com/list?b=2&a=1", "https://example.com/list?a=1&b=2"),
])
def test_url_key_same(a, b):
    assert dedupe.url_key(a) == dedupe.url_key(b)


@pytest.mark.parametrize("a, b", [
    ("https://example.com/post?id=1", "https://example.com/post?id=2"),
    ("https://example.com/post/1", "https://example.com/post/2"),
    ("https://example.com/Post", "https://example.com/post"),   # 경로는 대소문자를 구분
    ("https://a.example.com/1", "https://b.example.com/1"),
])
def test_url_key_different(a, b):
    assert dedupe.url_key(a) != dedupe.url_key(b)


@pytest.mark.parametrize("a, b", [
    ("겨울 오픈소스 해커톤 참가자 모집", "[공지] 겨울  오픈소스 해커톤 참가자 모집!"),
    ("겨울 오픈소스 해커톤 참가자 모집", "[학사][필독] 겨울 오픈소스 해커톤 참가자 모집"),
    ("2026 AI Hackathon 참가 안내", "２０２６ ai hackathon 참가안내"),
    ("제12회 데이터 분석 경진대회(~11/30)", "제12회 데이터 분석 경진대회 (~11.30)"),
])
def test_title_key_same(a, b):
    assert dedupe.title_key(make("x-1", a)) == dedupe.title_key(make("y-1", b)) != ""


def test_title_key_different_and_short():
    assert dedupe.title_key(make("x-1", "겨울 해커톤 참가자 모집")) != dedupe.title_key(make("x-2", "여름 해커톤 참가자 모집"))
    assert dedupe.title_key(make("x-1", "[공지] 채용")) == ""      # 너무 짧아 비교하지 않음
    assert dedupe.title_key(make("x-1", "[공지]")) == ""           # 머리말뿐인 제목도 오류 없이 처리


def test_title_key_jobs_includes_company():
    a = make("wanted-1", "백엔드 개발자 신입 채용", category="jobs", source="루프랩")
    b = make("jumpit-1", "백엔드 개발자 신입 채용", category="jobs", source="픽셀하우스")
    c = make("jumpit-2", "백엔드 개발자 신입 채용", category="jobs", source="루프랩")
    assert dedupe.title_key(a) != dedupe.title_key(b)
    assert dedupe.title_key(a) == dedupe.title_key(c)


# ── 1. 같은 실행 안 ───────────────────────────────────────────
def test_in_run_keeps_first():
    items = [make("jbnu-1", "첫 번째 제목입니다"), make("jbnu-2"), make("jbnu-1", "고정 공지로 또 나옴")]
    unique, dropped = dedupe.in_run(items)
    assert [it["id"] for it in unique] == ["jbnu-1", "jbnu-2"]
    assert unique[0]["title"] == "첫 번째 제목입니다"
    assert dropped == 1


# ── 2. 이미 저장한 글 ─────────────────────────────────────────
def test_existing_ids():
    table = FakeTable(rows=[{"id": "jbnu-1"}, {"id": "jbnu-3"}])
    items = [make("jbnu-1"), make("jbnu-2"), make("jbnu-3")]
    assert dedupe.existing_ids(table, items) == {"jbnu-1", "jbnu-3"}


def test_existing_ids_empty_makes_no_request():
    table = FakeTable()
    assert dedupe.existing_ids(table, []) == set()
    assert table.meta.client.batch_get_calls == []


def test_existing_ids_splits_into_batches_of_100():
    table = FakeTable(rows=[{"id": f"jbnu-{i}"} for i in range(0, 250, 2)])
    items = [make(f"jbnu-{i}") for i in range(250)]
    assert dedupe.existing_ids(table, items) == {f"jbnu-{i}" for i in range(0, 250, 2)}
    assert len(table.meta.client.batch_get_calls) == 3


def test_existing_ids_retries_unprocessed_keys(monkeypatch):
    monkeypatch.setattr(dedupe.time, "sleep", lambda s: None)
    table = FakeTable(rows=[{"id": f"jbnu-{i}"} for i in range(10)])
    table.unprocessed_first = True
    assert dedupe.existing_ids(table, [make(f"jbnu-{i}") for i in range(10)]) == {f"jbnu-{i}" for i in range(10)}
    assert len(table.meta.client.batch_get_calls) == 2


# ── 3. 다른 사이트의 같은 글 ──────────────────────────────────
def seen_table():
    return FakeTable(name="seen", key_name="seenKey")


def test_cross_site_drops_same_title_from_other_site():
    seen = seen_table()
    dedupe.record(seen, [make("devevent-aaa")])
    kept, dropped = dedupe.cross_site([make("jbnu-9", "[행사] 겨울 오픈소스 해커톤 참가자 모집")], seen)
    assert kept == [] and dropped == 1


def test_cross_site_drops_same_url_from_other_site():
    seen = seen_table()
    dedupe.record(seen, [make("devevent-aaa", "제목 하나 길게 씁니다", url="https://event.example.com/2026")])
    item = make("geeknews-5", "전혀 다른 제목을 길게 씁니다", url="http://www.event.example.com/2026/?utm_source=x")
    kept, dropped = dedupe.cross_site([item], seen)
    assert kept == [] and dropped == 1


def test_cross_site_keeps_same_title_from_same_site():
    """같은 학교가 매주 같은 제목으로 올리는 공지는 서로 다른 글."""
    seen = seen_table()
    dedupe.record(seen, [make("jbnu-1", "학생식당 주간 식단 안내입니다")])
    kept, dropped = dedupe.cross_site([make("jbnu-2", "학생식당 주간 식단 안내입니다")], seen)
    assert [it["id"] for it in kept] == ["jbnu-2"] and dropped == 0


def test_cross_site_within_one_run_first_site_wins():
    items = [make("devevent-aaa"), make("jbnu-9"), make("jbnu-10"), make("cbnu-3", "충북대 전용 공지사항입니다")]
    kept, dropped = dedupe.cross_site(items, seen_table())
    assert [it["id"] for it in kept] == ["devevent-aaa", "cbnu-3"]
    assert dropped == 2


def test_cross_site_without_table_compares_within_run():
    kept, dropped = dedupe.cross_site([make("devevent-aaa"), make("jbnu-9")], None)
    assert [it["id"] for it in kept] == ["devevent-aaa"] and dropped == 1


def test_cross_site_short_titles_are_not_compared():
    kept, _ = dedupe.cross_site([make("jbnu-1", "채용 공고"), make("cbnu-1", "채용 공고")], seen_table())
    assert len(kept) == 2


def test_record_writes_keys_with_ttl():
    seen = seen_table()
    dedupe.record(seen, [make("jbnu-1")], now=1_000_000)
    rows = list(seen.rows.values())
    assert len(rows) == 2                                    # 주소 키 + 제목 키
    assert {r["seenKey"][:2] for r in rows} == {"u#", "t#"}
    assert all(r["site"] == "jbnu" and r["itemId"] == "jbnu-1" for r in rows)
    assert all(r["expiresAt"] == 1_000_000 + dedupe.SEEN_TTL_DAYS * 86400 for r in rows)
