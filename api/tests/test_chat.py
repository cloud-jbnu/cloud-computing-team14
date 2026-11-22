import json
import urllib.error

import pytest
from botocore.exceptions import ClientError

import chat

TODAY = "2026-11-22"
ITEMS = [
    {"id": "c1", "category": "contest", "subtype": "해커톤", "source": "GDG", "title": "AI 해커톤", "date": "2026-11-20",
     "deadline": "2026-11-25", "fields": ["ai"], "url": "https://example.com/c1", "summary": ["팀 3~4인", "온라인 접수"]},
    {"id": "c2", "category": "contest", "subtype": "공모전", "source": "예시", "title": "마감 지난 대회", "date": "2026-11-01",
     "deadline": "2026-11-10", "fields": [], "url": "https://example.com/c2"},
    {"id": "u1", "category": "univ", "subtype": "전북대", "source": "전북대 학생과", "title": "장학금 신청 안내", "date": "2026-11-21",
     "fields": [], "url": "https://example.com/u1"},
]


def fake_post(result):
    """Gemini 응답 대신 result(dict)를 돌려주고, 받은 요청을 calls에 적어 두는 가짜 호출."""
    calls = []

    def post(url, payload, api_key, timeout):
        calls.append({"url": url, "payload": payload, "key": api_key})
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(result, ensure_ascii=False)}]}}]}
    post.calls = calls
    return post


# ── 입력 정리 ──────────────────────────────────────────────────
def test_clean_message_limits_length():
    assert chat.clean_message("  해커톤 알려줘 ") == "해커톤 알려줘"
    assert chat.clean_message("   ") is None
    assert chat.clean_message("가" * (chat.MAX_MESSAGE + 1)) is None
    assert chat.clean_message(123) is None


def test_clean_history_keeps_recent_valid_turns_starting_with_user():
    raw = [{"role": "model", "text": "인사"}] + [
        {"role": "user" if i % 2 == 0 else "model", "text": f"말 {i}"} for i in range(10)
    ] + [{"role": "system", "text": "무시"}, {"role": "user", "text": ""}, "이상한 값"]
    history = chat.clean_history(raw)
    assert len(history) <= chat.MAX_HISTORY
    assert history[0]["role"] == "user"
    assert all(t["role"] in ("user", "model") and t["text"] for t in history)
    assert history[-1]["text"] == "말 9"
    assert chat.clean_history("문자열") == []


# ── 글 고르기 ──────────────────────────────────────────────────
def test_open_items_drops_past_deadlines_only():
    ids = [it["id"] for it in chat.open_items(ITEMS, TODAY)]
    assert ids == ["c1", "u1"]


def test_compact_drops_empty_values_and_joins_summary():
    row = chat.compact(ITEMS[2])
    assert "deadline" not in row and "fields" not in row and "url" not in row
    assert chat.compact(ITEMS[0])["summary"] == "팀 3~4인 온라인 접수"


def test_pick_items_ignores_unknown_and_duplicate_ids():
    picked = chat.pick_items(["u1", "없는 글", "u1", 7, "c1"], ITEMS)
    assert [it["id"] for it in picked] == ["u1", "c1"]
    assert chat.pick_items(None, ITEMS) == []


def test_answer_sends_only_open_items_and_returns_cards():
    post = fake_post({"answer": " 이번 주 마감인 해커톤이 있어요. ", "item_ids": ["c1", "c2"]})
    result = chat.answer("이번 주 마감 해커톤?", [{"role": "user", "text": "안녕"}, {"role": "model", "text": "네"}],
                         ITEMS, "KEY", "gemini-test", today=TODAY, post=post)
    assert result["answer"] == "이번 주 마감인 해커톤이 있어요."
    assert [it["id"] for it in result["items"]] == ["c1"]  # c2는 마감이 지나 목록에 없었으므로 버림

    call = post.calls[0]
    assert "gemini-test" in call["url"] and call["key"] == "KEY"
    contents = call["payload"]["contents"]
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    last = contents[-1]["parts"][0]["text"]
    assert '"c1"' in last and '"c2"' not in last and "질문: 이번 주 마감 해커톤?" in last
    assert TODAY in call["payload"]["systemInstruction"]["parts"][0]["text"]


def test_ask_gemini_rejects_bad_shape():
    with pytest.raises(chat.ChatError):
        chat.ask_gemini({}, "KEY", "m", post=fake_post({"item_ids": []}))


def test_ask_gemini_retries_once_on_429(monkeypatch):
    monkeypatch.setattr(chat.time, "sleep", lambda s: None)
    ok = fake_post({"answer": "됐어요", "item_ids": []})
    attempts = []

    def post(url, payload, api_key, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(url, 429, "too many", None, None)
        return ok(url, payload, api_key, timeout)

    assert chat.ask_gemini({}, "KEY", "m", post=post)["answer"] == "됐어요"
    assert len(attempts) == 2


def test_ask_gemini_does_not_retry_on_400():
    attempts = []

    def post(url, payload, api_key, timeout):
        attempts.append(1)
        raise urllib.error.HTTPError(url, 400, "bad", None, None)

    with pytest.raises(chat.ChatError):
        chat.ask_gemini({}, "KEY", "m", post=post)
    assert len(attempts) == 1


# ── 하루 질문 수 ───────────────────────────────────────────────
class FakeUsageTable:
    def __init__(self):
        self.counts = {}

    def update_item(self, Key, ExpressionAttributeValues, **_):
        key = Key["userDay"]
        if self.counts.get(key, 0) >= ExpressionAttributeValues[":limit"]:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        self.counts[key] = self.counts.get(key, 0) + 1
        return {"Attributes": {"count": self.counts[key]}}


def test_take_quota_counts_down_per_user_and_day():
    table = FakeUsageTable()
    assert chat.take_quota(table, "u", TODAY, limit=2) == 1
    assert chat.take_quota(table, "u", TODAY, limit=2) == 0
    assert chat.take_quota(table, "u", TODAY, limit=2) is None
    assert chat.take_quota(table, "u", "2026-11-23", limit=2) == 1   # 다음 날은 새로
    assert chat.take_quota(table, "other", TODAY, limit=2) == 1      # 다른 사람은 따로


# ── 진입점 ─────────────────────────────────────────────────────
def event(body=None, sub="user-sub"):
    claims = {"sub": sub} if sub else {}
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}, "body": json.dumps(body or {})}


def test_handler_requires_login(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "KEY")
    assert chat.lambda_handler({"requestContext": {}}, None)["statusCode"] == 401


def test_handler_without_key_is_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert chat.lambda_handler(event({"message": "안녕"}), None)["statusCode"] == 503


def test_handler_rejects_empty_message(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "KEY")
    res = chat.lambda_handler(event({"message": "  "}), None)
    assert res["statusCode"] == 400
    assert "질문" in json.loads(res["body"])["message"]
