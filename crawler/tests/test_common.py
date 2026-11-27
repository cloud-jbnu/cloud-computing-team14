from datetime import date

import pytest
import requests

from common import http, item


# ── http ──────────────────────────────────────────────────────
class FakeResponse:
    def __init__(self, status=200, text="ok", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"
        self.apparent_encoding = "euc-kr"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """미리 정해 둔 결과(응답 또는 예외)를 순서대로 돌려줍니다."""
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def fake_http(monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda s: None)

    def install(results):
        session = FakeSession(results)
        monkeypatch.setattr(http, "_session", session)
        return session
    return install


def test_get_sets_timeout(fake_http):
    session = fake_http([FakeResponse()])
    http.get("https://example.com")
    assert session.calls[0][1]["timeout"] == http.TIMEOUT


def test_get_retries_on_5xx_then_succeeds(fake_http):
    session = fake_http([FakeResponse(503), FakeResponse(200)])
    assert http.get("https://example.com").status_code == 200
    assert len(session.calls) == 2


def test_get_retries_on_connection_error(fake_http):
    session = fake_http([requests.ConnectionError("끊김"), requests.Timeout("늦음"), FakeResponse(200)])
    assert http.get("https://example.com").status_code == 200
    assert len(session.calls) == 3


def test_get_gives_up_after_retries(fake_http):
    session = fake_http([FakeResponse(500)] * 3)
    with pytest.raises(requests.HTTPError):
        http.get("https://example.com")
    assert len(session.calls) == http.RETRIES + 1


def test_get_does_not_retry_4xx(fake_http):
    session = fake_http([FakeResponse(404), FakeResponse(200)])
    with pytest.raises(requests.HTTPError):
        http.get("https://example.com")
    assert len(session.calls) == 1


def test_get_html_guesses_encoding_when_header_has_none(fake_http):
    res = FakeResponse(headers={"Content-Type": "text/html"})
    fake_http([res])
    http.get_html("https://example.com")
    assert res.encoding == "euc-kr"


def test_get_html_keeps_declared_encoding(fake_http):
    res = FakeResponse()
    fake_http([res])
    http.get_html("https://example.com")
    assert res.encoding == "utf-8"


# ── item ──────────────────────────────────────────────────────
def test_make_id():
    assert item.make_id("jbnu", 12345) == "jbnu-12345"
    assert item.make_id("github", "astral-sh/uv") == "github-astral-sh-uv"
    with pytest.raises(ValueError):
        item.make_id("jbnu", " ")


def test_hash_id_is_stable():
    a = item.hash_id("devevent", "https://example.com/a")
    assert a == item.hash_id("devevent", " https://example.com/a ")
    assert a != item.hash_id("devevent", "https://example.com/b")
    assert a.startswith("devevent-") and len(a) == len("devevent-") + 12


BASE = date(2026, 11, 17)


@pytest.mark.parametrize("text, expected", [
    ("2026-11-17", "2026-11-17"),
    ("2026.11.17", "2026-11-17"),
    ("2026. 11. 7.", "2026-11-07"),
    ("2026/1/5", "2026-01-05"),
    ("2026년 11월 17일", "2026-11-17"),
    ("2026-11-17T09:30:00+09:00", "2026-11-17"),
    ("작성일 2026.11.17 조회 12", "2026-11-17"),
    ("26.11.17", "2026-11-17"),
    ("11.17", "2026-11-17"),
    ("11-05", "2026-11-05"),
    ("11월 5일", "2026-11-05"),
    ("12.28", "2025-12-28"),   # 한 달 넘게 미래 → 작년
    ("12.10", "2026-12-10"),   # 한 달 이내 미래는 올해 (마감일 등)
])
def test_parse_date(text, expected):
    assert item.parse_date(text, base=BASE) == expected


@pytest.mark.parametrize("text", ["", None, "상시", "2026-13-40", "새 글"])
def test_parse_date_unreadable(text):
    assert item.parse_date(text, base=BASE) is None


@pytest.mark.parametrize("text, expected", [
    ("서울 강서구", "서울"), ("경기도 성남시", "경기"), ("전북특별자치도 전주시", "전북"),
    ("경상남도 창원시", "경남"), ("충청북도", "충북"), ("재택", None), ("", None), (None, None),
])
def test_region_of(text, expected):
    assert item.region_of(text) == expected


def test_regions_of_keeps_order_without_duplicates():
    assert item.regions_of(["경기 성남시", "서울 강남구", "경기 판교", "원격"]) == ["경기", "서울"]
