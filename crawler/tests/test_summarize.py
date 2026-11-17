import json

import pytest
import requests

import summarize


class FakeResponse:
    def __init__(self, status=200, rows=None, text=None):
        self.status_code = status
        self._body = {"candidates": [{"content": {"parts": [{"text": text if text is not None else json.dumps(rows or [])}]}}]}
        self.text = "오류 내용"

    def json(self):
        return self._body


class FakeSession:
    """정해 둔 결과를 순서대로 돌려줍니다. 함수면 요청에 담긴 글 목록을 넘겨 응답을 만들게 합니다."""
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def post(self, url, json=None, timeout=None, headers=None):
        entries = __import__("json").loads(json["contents"][0]["parts"][0]["text"])
        self.calls.append({"url": url, "payload": json, "headers": headers, "entries": entries})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result(entries) if callable(result) else result


def echo(entries):
    """받은 글마다 요약 2줄을 돌려주는 정상 응답."""
    return FakeResponse(rows=[{"id": e["id"], "summary": [f"{e['id']} 요약 1", "요약 2"], "fields": ["ai"]} for e in entries])


def make(n, prefix="jbnu"):
    return [{"id": f"{prefix}-{i}", "category": "univ", "source": "전북대", "title": f"글 {i}", "fields": []} for i in range(n)]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(summarize.time, "sleep", lambda s: None)


def run(items, results, bodies=None, key="키"):
    session = FakeSession(results)
    return summarize.summarize(items, bodies or {}, api_key=key, model="테스트모델", session=session), session


# ── 요청 ──────────────────────────────────────────────────────
def test_no_key_makes_no_request():
    results, session = run(make(3), [], key="")
    assert results == {} and session.calls == []


def test_no_items_makes_no_request():
    results, session = run([], [])
    assert results == {} and session.calls == []


def test_request_shape():
    items = make(1)
    _, session = run(items, [echo], bodies={"jbnu-0": "본문" * 2000})
    call = session.calls[0]
    assert call["url"].endswith("/models/테스트모델:generateContent")
    assert call["headers"] == {"x-goog-api-key": "키"} and "키" not in call["url"]
    config = call["payload"]["generationConfig"]
    assert config["responseMimeType"] == "application/json" and config["responseSchema"] == summarize.RESPONSE_SCHEMA
    entry = call["entries"][0]
    assert set(entry) == {"id", "category", "source", "title", "body"}
    assert len(entry["body"]) == summarize.MAX_BODY_CHARS          # 긴 본문은 자름


def test_missing_body_is_sent_as_empty():
    _, session = run(make(1), [echo])
    assert session.calls[0]["entries"][0]["body"] == ""


def test_batches_of_ten():
    results, session = run(make(23), [echo, echo, echo])
    assert [len(c["entries"]) for c in session.calls] == [10, 10, 3]
    assert len(results) == 23


# ── 재시도 · 실패 ─────────────────────────────────────────────
def test_retries_on_429_and_5xx():
    results, session = run(make(2), [FakeResponse(429), FakeResponse(503), echo])
    assert len(session.calls) == 3 and len(results) == 2


def test_retries_on_connection_error():
    results, session = run(make(2), [requests.ConnectionError("끊김"), echo])
    assert len(session.calls) == 2 and len(results) == 2


def test_does_not_retry_bad_key():
    results, session = run(make(2), [FakeResponse(403), echo])
    assert len(session.calls) == 1 and results == {}


def test_failed_batch_does_not_stop_the_rest():
    results, session = run(make(15), [FakeResponse(400), echo])
    assert sorted(results) == sorted(f"jbnu-{i}" for i in range(10, 15))


def test_unreadable_response_is_skipped():
    results, _ = run(make(2), [FakeResponse(text="JSON이 아님")])
    assert results == {}


# ── 응답 정리 ─────────────────────────────────────────────────
def test_partial_and_malformed_rows():
    rows = [
        {"id": "jbnu-0", "summary": ["  - 첫 줄  ", "", "둘째\n줄", "셋째", "넷째"], "fields": ["ai", "없는분야", "cloud"]},
        {"id": "jbnu-1", "summary": "배열이 아님", "fields": []},
        {"id": "jbnu-2", "summary": [], "fields": []},
        {"id": "남의글-9", "summary": ["요청하지 않은 id"], "fields": []},
        {"id": "jbnu-0", "summary": ["같은 id가 또 옴"], "fields": []},
        "딕셔너리 아님",
        {"id": "jbnu-3", "summary": ["가" * 500], "fields": "배열 아님"},
    ]
    results, _ = run(make(5), [FakeResponse(rows=rows)])
    assert sorted(results) == ["jbnu-0", "jbnu-3"]                  # jbnu-4는 응답에 없어서 빠짐
    assert results["jbnu-0"] == {"summary": ["첫 줄", "둘째 줄", "셋째"], "fields": ["ai", "cloud"]}
    assert results["jbnu-3"] == {"summary": ["가" * summarize.MAX_LINE_CHARS], "fields": []}


def test_response_that_is_not_a_list():
    results, _ = run(make(1), [FakeResponse(text='{"id": "jbnu-0"}')])
    assert results == {}


def test_apply_merges_fields_and_leaves_unsummarized_items():
    items = [
        {"id": "a-1", "fields": ["cloud"]},
        {"id": "a-2", "fields": ["cloud"]},
    ]
    summarize.apply(items, {"a-1": {"summary": ["요약"], "fields": ["ai", "cloud"]}})
    assert items[0] == {"id": "a-1", "fields": ["ai", "cloud"], "summary": ["요약"]}
    assert items[1] == {"id": "a-2", "fields": ["cloud"]}            # 요약 실패한 글은 그대로
