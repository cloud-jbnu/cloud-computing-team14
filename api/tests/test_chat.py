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

SEARCH_RESPONSE = {
    "candidates": [{
        "content": {"parts": [{"text": "하버드대는 "}, {"text": "12월에 해커톤을 열어요."}]},
        "groundingMetadata": {
            "groundingChunks": [
                {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a", "title": "harvard.edu"}},
                {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a", "title": "중복"}},
                {"web": {"uri": "javascript:alert(1)", "title": "나쁜 주소"}},
                {"retrievedContext": {}},
            ],
            "searchEntryPoint": {"renderedContent": "<div class=\"chip\">harvard hackathon</div>"},
        },
    }],
}


def gemini_text(result):
    """구조화 응답(JSON 문자열)을 담은 Gemini 응답 모양."""
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(result, ensure_ascii=False)}]}}]}


def fake_post(*responses):
    """부를 때마다 responses를 차례로 돌려주고(예외면 던지고), 받은 요청을 calls에 적어 두는 가짜 호출."""
    calls, queue = [], list(responses)

    def post(url, payload, api_key, timeout):
        calls.append({"url": url, "payload": payload, "key": api_key, "timeout": timeout})
        r = queue.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
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
    assert [it["id"] for it in chat.open_items(ITEMS, TODAY)] == ["c1", "u1"]


def test_compact_drops_empty_values_and_joins_summary():
    row = chat.compact(ITEMS[2])
    assert "deadline" not in row and "fields" not in row and "url" not in row
    assert chat.compact(ITEMS[0])["summary"] == "팀 3~4인 온라인 접수"


def test_pick_items_ignores_unknown_and_duplicate_ids():
    picked = chat.pick_items(["u1", "없는 글", "u1", 7, "c1"], ITEMS)
    assert [it["id"] for it in picked] == ["u1", "c1"]
    assert chat.pick_items(None, ITEMS) == []


# ── 1단계: 모아 둔 글로 답하기 ─────────────────────────────────
def test_answer_sends_only_open_items_and_returns_cards():
    post = fake_post(gemini_text({"answer": " 이번 주 마감인 해커톤이 있어요. ", "item_ids": ["c1", "c2"], "need_web_search": False}))
    result = chat.answer("이번 주 마감 해커톤?", [{"role": "user", "text": "안녕"}, {"role": "model", "text": "네"}],
                         ITEMS, "KEY", "gemini-test", today=TODAY, post=post)
    assert result["answer"] == "이번 주 마감인 해커톤이 있어요."
    assert [it["id"] for it in result["items"]] == ["c1"]  # c2는 마감이 지나 목록에 없었으므로 버림
    assert result["need_web_search"] is False

    call = post.calls[0]
    assert "gemini-test" in call["url"] and call["key"] == "KEY"
    contents = call["payload"]["contents"]
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    last = contents[-1]["parts"][0]["text"]
    assert '"c1"' in last and '"c2"' not in last and "질문: 이번 주 마감 해커톤?" in last
    assert TODAY in call["payload"]["systemInstruction"]["parts"][0]["text"]
    assert "tools" not in call["payload"]  # 1단계는 검색하지 않음


def test_need_web_search_must_be_true_exactly():
    post = fake_post(gemini_text({"answer": "없어요", "item_ids": [], "need_web_search": "true"}))
    assert chat.answer("하버드", [], ITEMS, "K", "m", today=TODAY, post=post)["need_web_search"] is False


def test_parse_answer_rejects_bad_shape():
    with pytest.raises(chat.ChatError):
        chat.parse_answer(gemini_text({"item_ids": []}))
    with pytest.raises(chat.ChatError):
        chat.parse_answer({"candidates": [{"content": {"parts": [{"text": "JSON 아님"}]}}]})


def test_call_gemini_retries_once_on_429(monkeypatch):
    monkeypatch.setattr(chat.time, "sleep", lambda s: None)
    post = fake_post(urllib.error.HTTPError("u", 429, "too many", None, None), {"ok": 1})
    assert chat.call_gemini({}, "KEY", "m", post=post) == {"ok": 1}
    assert len(post.calls) == 2


def test_call_gemini_does_not_retry_on_400_or_when_retry_off():
    post = fake_post(urllib.error.HTTPError("u", 400, "bad", None, None))
    with pytest.raises(chat.ChatError):
        chat.call_gemini({}, "KEY", "m", post=post)
    post = fake_post(urllib.error.HTTPError("u", 503, "busy", None, None))
    with pytest.raises(chat.ChatError):
        chat.call_gemini({}, "KEY", "m", post=post, retry=False)
    assert len(post.calls) == 1


# ── 2단계: 웹 검색 ─────────────────────────────────────────────
def test_web_search_turns_on_google_search_and_reads_sources():
    post = fake_post(SEARCH_RESPONSE)
    web = chat.web_search("하버드대 해커톤 알려줘", [{"role": "user", "text": "안녕"}], "KEY", "m", today=TODAY, post=post)
    payload = post.calls[0]["payload"]
    assert payload["tools"] == [{"google_search": {}}]
    assert "responseSchema" not in payload["generationConfig"]  # 검색과 JSON 스키마는 같이 쓰지 않음
    assert payload["contents"][-1]["parts"][0]["text"] == "하버드대 해커톤 알려줘"

    assert web["answer"] == "하버드대는 12월에 해커톤을 열어요."
    assert web["sources"] == [{"title": "harvard.edu", "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a"}]
    assert "harvard hackathon" in web["suggestionsHtml"]


def test_parse_search_without_grounding_metadata():
    web = chat.parse_search({"candidates": [{"content": {"parts": [{"text": "답"}]}}]})
    assert web == {"answer": "답", "sources": [], "suggestionsHtml": ""}
    with pytest.raises(chat.ChatError):
        chat.parse_search({"candidates": [{"content": {"parts": [{"text": "  "}]}}]})


# ── 하루 사용량 ────────────────────────────────────────────────
class FakeUsageTable:
    def __init__(self):
        self.counts = {}

    def update_item(self, Key, ExpressionAttributeValues, ConditionExpression=None, **_):
        key = Key["userDay"]
        if ":minus" in ExpressionAttributeValues:
            self.counts[key] = self.counts.get(key, 0) - 1
            return {}
        if self.counts.get(key, 0) >= ExpressionAttributeValues[":limit"]:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        self.counts[key] = self.counts.get(key, 0) + 1
        return {"Attributes": {"count": self.counts[key]}}


def test_take_quota_counts_down_per_key():
    table = FakeUsageTable()
    assert chat.take_quota(table, chat.question_key("u", TODAY), 2) == 1
    assert chat.take_quota(table, chat.question_key("u", TODAY), 2) == 0
    assert chat.take_quota(table, chat.question_key("u", TODAY), 2) is None
    assert chat.take_quota(table, chat.question_key("u", "2026-11-23"), 2) == 1   # 다음 날은 새로
    assert chat.take_quota(table, chat.question_key("other", TODAY), 2) == 1      # 다른 사람은 따로


def test_search_quota_per_user_then_global():
    table = FakeUsageTable()
    assert chat.take_search_quota(table, "a", TODAY, per_user=1, per_day=2) is None
    assert "하루 1번" in chat.take_search_quota(table, "a", TODAY, per_user=1, per_day=2)   # a는 다 씀
    assert chat.take_search_quota(table, "b", TODAY, per_user=1, per_day=2) is None
    notice = chat.take_search_quota(table, "c", TODAY, per_user=1, per_day=2)              # 전체 한도 참
    assert "사이트 전체" in notice
    user_c, global_key = chat.search_keys("c", TODAY)
    assert table.counts[user_c] == 0          # 못 쓴 c의 사용자 몫은 되돌림
    assert table.counts[global_key] == 2


# ── 진입점 ─────────────────────────────────────────────────────
def event(body=None, sub="user-sub"):
    claims = {"sub": sub} if sub else {}
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}, "body": json.dumps(body or {})}


class FakeItemsTable:
    def query(self, KeyConditionExpression, **_):
        category = KeyConditionExpression.get_expression()["values"][1]
        return {"Items": [it for it in ITEMS if it["category"] == category]}


@pytest.fixture
def handler_env(monkeypatch):
    """Lambda 환경을 흉내 냅니다: 가짜 DynamoDB와 가짜 Gemini 호출."""
    import boto3

    usage, items = FakeUsageTable(), FakeItemsTable()

    class FakeDB:
        def Table(self, name):
            return usage if name == "usage" else items

    monkeypatch.setattr(boto3, "resource", lambda *_a, **_k: FakeDB())
    monkeypatch.setenv("GEMINI_API_KEY", "KEY")
    monkeypatch.setenv("CHAT_USAGE_TABLE", "usage")
    monkeypatch.setenv("ITEMS_TABLE", "items")
    monkeypatch.setenv("CHAT_SEARCH_PER_USER", "1")
    monkeypatch.setenv("CHAT_SEARCH_PER_DAY", "10")
    monkeypatch.setattr(chat, "today_kst", lambda: TODAY)
    chat._cache.update(at=0.0, items=[])

    def use(*responses):
        post = fake_post(*responses)
        monkeypatch.setattr(chat, "_post", post)
        return post
    use.usage = usage
    return use


def call(body):
    res = chat.lambda_handler(event(body), None)
    return res["statusCode"], json.loads(res["body"])


def test_handler_answers_from_collected_posts_without_search(handler_env):
    post = handler_env(gemini_text({"answer": "해커톤이 있어요.", "item_ids": ["c1"], "need_web_search": False}))
    status, body = call({"message": "해커톤 있어?"})
    assert status == 200
    assert body["answer"] == "해커톤이 있어요." and [it["id"] for it in body["items"]] == ["c1"]
    assert body["web"] is None and body["notice"] is None and body["remaining"] == chat.DAILY_LIMIT - 1
    assert "need_web_search" not in body
    assert len(post.calls) == 1


def test_handler_searches_web_when_needed(handler_env):
    post = handler_env(gemini_text({"answer": "모아 둔 글 중에는 하버드대 글이 없어요.", "item_ids": [], "need_web_search": True}),
                       SEARCH_RESPONSE)
    status, body = call({"message": "하버드대 해커톤 알려줘"})
    assert status == 200
    assert body["web"]["answer"] == "하버드대는 12월에 해커톤을 열어요."
    assert body["web"]["sources"][0]["title"] == "harvard.edu"
    assert body["notice"] is None
    assert post.calls[1]["payload"]["tools"] == [{"google_search": {}}]


def test_handler_skips_search_when_user_limit_used(handler_env):
    handler_env(gemini_text({"answer": "없어요.", "item_ids": [], "need_web_search": True}), SEARCH_RESPONSE,
                gemini_text({"answer": "없어요.", "item_ids": [], "need_web_search": True}))
    assert call({"message": "하버드"})[1]["web"] is not None
    status, body = call({"message": "스탠퍼드"})        # 사용자 한도 1번을 이미 씀 → 검색 안 함
    assert status == 200 and body["web"] is None and "하루 1번" in body["notice"]


def test_handler_keeps_answer_when_search_fails(handler_env):
    handler_env(gemini_text({"answer": "없어요.", "item_ids": [], "need_web_search": True}),
                urllib.error.HTTPError("u", 400, "grounding not allowed", None, None))
    status, body = call({"message": "하버드"})
    assert status == 200 and body["answer"] == "없어요." and body["web"] is None
    assert "웹 검색에 실패" in body["notice"]


def test_handler_search_off_when_limit_zero(handler_env, monkeypatch):
    monkeypatch.setenv("CHAT_SEARCH_PER_DAY", "0")
    post = handler_env(gemini_text({"answer": "없어요.", "item_ids": [], "need_web_search": True}))
    status, body = call({"message": "하버드"})
    assert status == 200 and body["web"] is None and body["notice"] is None and len(post.calls) == 1


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
