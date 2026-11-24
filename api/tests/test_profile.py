import json

import pytest

import user_profile
from claims import discord_id, user_sub


# ── 토큰 클레임 ────────────────────────────────────────────────
def event(claims=None, method="GET", body=None):
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": claims or {}}}, "http": {"method": method}},
        "body": json.dumps(body) if body is not None else None,
    }


@pytest.mark.parametrize("claims, want", [
    ({"username": "Discord_123456789", "cognito:groups": "[us-east-1_AbC123_Discord]"}, "123456789"),
    ({"username": "discord_123456789", "cognito:groups": "[us-east-1_AbC123_Discord admins]"}, "123456789"),
    ({"username": "discord_123456789"}, None),                       # 이메일 가입자가 이름만 흉내
    ({"username": "test@example.com"}, None),
    ({"username": "discord_abc", "cognito:groups": "[us-east-1_AbC123_Discord]"}, None),
    ({}, None),
])
def test_discord_id(claims, want):
    assert discord_id(event(claims)) == want


def test_user_sub():
    assert user_sub(event({"sub": "abc"})) == "abc"
    assert user_sub({}) is None


# ── 입력 검사 ──────────────────────────────────────────────────
def test_clean_accepts_known_school_other_and_null():
    assert user_profile.clean({"school": "전북대"}) == {"school": "전북대", "requestedSchool": None}
    assert user_profile.clean({"school": "other", "requestedSchool": "  서울   대학교 "}) == {"school": "other", "requestedSchool": "서울 대학교"}
    assert user_profile.clean({"school": "other", "requestedSchool": "가" * 50})["requestedSchool"] == "가" * user_profile.MAX_REQUEST
    assert user_profile.clean({"school": None}) == {"school": None, "requestedSchool": None}
    # requestedSchool은 other일 때만 저장
    assert user_profile.clean({"school": "부산대", "requestedSchool": "서울대"})["requestedSchool"] is None


def test_clean_rejects_unknown_school():
    with pytest.raises(ValueError):
        user_profile.clean({"school": "하버드대"})


# ── 저장 ───────────────────────────────────────────────────────
class FakeTable:
    def __init__(self):
        self.rows = {}

    def get_item(self, Key):
        row = self.rows.get(Key["userId"])
        return {"Item": row} if row else {}

    def put_item(self, Item):
        self.rows[Item["userId"]] = dict(Item)

    def delete_item(self, Key):
        self.rows.pop(Key["userId"], None)


@pytest.fixture
def table(monkeypatch):
    import boto3

    t = FakeTable()

    class FakeDB:
        def Table(self, name):
            assert name == "profiles"
            return t

    monkeypatch.setattr(boto3, "resource", lambda *_a, **_k: FakeDB())
    monkeypatch.setenv("PROFILES_TABLE", "profiles")
    return t


def call(e):
    res = user_profile.lambda_handler(e, None)
    return res["statusCode"], json.loads(res["body"])


DISCORD = {"sub": "sub-d", "username": "Discord_42", "cognito:groups": "[us-east-1_X_Discord]"}
EMAIL = {"sub": "sub-e", "username": "me@example.com"}


def test_get_without_profile_is_empty(table):
    assert call(event(EMAIL)) == (200, {"school": None, "requestedSchool": None})


def test_put_then_get_and_discord_id_saved(table):
    assert call(event(DISCORD, "PUT", {"school": "경북대"})) == (200, {"school": "경북대", "requestedSchool": None})
    assert table.rows["sub-d"]["discordId"] == "42"     # 크롤러가 DM 보낼 때 찾을 수 있게
    assert call(event(DISCORD)) == (200, {"school": "경북대", "requestedSchool": None})

    call(event(EMAIL, "PUT", {"school": "other", "requestedSchool": "서울대"}))
    assert "discordId" not in table.rows["sub-e"]
    assert table.rows["sub-e"]["requestedSchool"] == "서울대"


def test_put_null_removes_row(table):
    call(event(EMAIL, "PUT", {"school": "전북대"}))
    assert call(event(EMAIL, "PUT", {"school": None})) == (200, {"school": None, "requestedSchool": None})
    assert "sub-e" not in table.rows


def test_bad_requests(table):
    assert call(event(EMAIL, "PUT", {"school": "하버드대"}))[0] == 400
    bad = event(EMAIL, "PUT")
    bad["body"] = "{JSON 아님"
    assert call(bad)[0] == 400
    assert call(event(EMAIL, "DELETE"))[0] == 405
    assert call(event({}, "GET"))[0] == 401
