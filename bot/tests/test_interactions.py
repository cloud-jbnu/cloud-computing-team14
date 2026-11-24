import base64
import json

import pytest
from nacl.signing import SigningKey

import interactions
import register

KEY = SigningKey.generate()                      # 디스코드 역할: 이 키로 요청에 서명
PUBLIC_KEY = KEY.verify_key.encode().hex()       # 개발자 포털의 Public Key 역할
ME = "123456789012345678"


def signed_event(payload, key=KEY, timestamp="1700000000", base64_body=False, tamper=False):
    """디스코드가 API Gateway(HTTP API)를 거쳐 Lambda에 보내는 요청 모양."""
    body = json.dumps(payload, ensure_ascii=False)
    signature = key.sign(timestamp.encode() + body.encode("utf-8")).signature.hex()
    if tamper:
        body = body.replace("구독", "해지")
    return {
        "headers": {"x-signature-ed25519": signature, "x-signature-timestamp": timestamp, "content-type": "application/json"},
        "body": base64.b64encode(body.encode("utf-8")).decode() if base64_body else body,
        "isBase64Encoded": base64_body,
    }


def command(name, keyword=None, user_id=ME, in_guild=True, kind=interactions.COMMAND, focused=False):
    user = {"id": user_id, "username": "tester"}
    data = {"name": name, "type": 1}
    if keyword is not None:
        data["options"] = [{"name": "키워드", "type": 3, "value": keyword, **({"focused": True} if focused else {})}]
    return {"type": kind, "data": data, **({"member": {"user": user}} if in_guild else {"user": user})}


@pytest.fixture
def call(monkeypatch, table):
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", PUBLIC_KEY)
    monkeypatch.setattr(interactions, "_table", table)

    def call(event):
        res = interactions.lambda_handler(event, None)
        return res["statusCode"], json.loads(res["body"])
    return call


# ── 서명 검사 ──────────────────────────────────────────────────
def test_ping(call):
    assert call(signed_event({"type": 1})) == (200, {"type": 1})


def test_ping_works_without_table(monkeypatch):
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", PUBLIC_KEY)
    monkeypatch.setattr(interactions, "_table", None)
    monkeypatch.delenv("SUBSCRIPTIONS_TABLE", raising=False)
    assert interactions.lambda_handler(signed_event({"type": 1}), None)["statusCode"] == 200


def test_rejects_bad_signatures(call, table):
    payload = command("구독", "해커톤")
    assert call(signed_event(payload, key=SigningKey.generate()))[0] == 401   # 다른 키로 서명
    assert call(signed_event(payload, tamper=True))[0] == 401                 # 서명 뒤에 본문이 바뀜
    event = signed_event(payload)
    event["headers"]["x-signature-timestamp"] = "1700000001"                  # 시각이 바뀜
    assert call(event)[0] == 401
    for broken in ({"x-signature-ed25519": "zz"}, {"x-signature-ed25519": "abcd"}, {"x-signature-ed25519": None}):
        event = signed_event(payload)
        event["headers"].update(broken)
        assert call(event)[0] == 401
    no_headers = signed_event(payload)
    no_headers["headers"] = None
    assert call(no_headers)[0] == 401
    assert table.rows == set()   # 거부한 요청은 아무것도 바꾸지 않음


def test_rejects_everything_without_public_key(call, monkeypatch):
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", "")
    assert call(signed_event({"type": 1}))[0] == 401


def test_header_names_are_case_insensitive_and_body_may_be_base64(call):
    event = signed_event({"type": 1}, base64_body=True)
    event["headers"] = {k.title(): v for k, v in event["headers"].items()}
    assert call(event) == (200, {"type": 1})


def test_signed_but_not_json(call):
    body, timestamp = "not json", "1"
    event = {"headers": {"x-signature-ed25519": KEY.sign(timestamp.encode() + body.encode()).signature.hex(),
                         "x-signature-timestamp": timestamp}, "body": body}
    assert call(event)[0] == 400


# ── 명령어 ─────────────────────────────────────────────────────
def test_commands_roundtrip(call, table):
    status, res = call(signed_event(command("구독", "해커톤")))
    assert status == 200 and res["type"] == interactions.MESSAGE
    assert res["data"]["flags"] == interactions.EPHEMERAL          # 본인에게만 보임
    assert res["data"]["allowed_mentions"] == {"parse": []}        # 키워드에 @everyone을 넣어도 멘션 안 됨
    assert "구독을 시작했어요" in res["data"]["content"]
    assert table.rows == {(ME, "해커톤")}                           # userId는 문자열

    call(signed_event(command("구독", "CTF", in_guild=False)))      # 봇과의 DM에서 쓴 명령어
    assert "`CTF`, `해커톤`" in call(signed_event(command("목록")))[1]["data"]["content"]
    assert "해지했어요" in call(signed_event(command("해지", "해커톤")))[1]["data"]["content"]
    assert table.rows == {(ME, "CTF")}


def test_autocomplete_lists_my_keywords(call, table):
    table.rows = {(ME, "해커톤"), (ME, "장학금"), ("999", "남의 것")}
    status, res = call(signed_event(command("해지", "해", kind=interactions.AUTOCOMPLETE, focused=True)))
    assert (status, res) == (200, {"type": interactions.CHOICES, "data": {"choices": [{"name": "해커톤", "value": "해커톤"}]}})


def test_db_error_becomes_a_message(call, table):
    table.fail = True
    status, res = call(signed_event(command("목록")))
    assert status == 200 and "처리하지 못했어요" in res["data"]["content"]
    status, res = call(signed_event(command("해지", "", kind=interactions.AUTOCOMPLETE, focused=True)))
    assert (status, res["data"]["choices"]) == (200, [])


def test_missing_user(call):
    payload = command("목록")
    del payload["member"]
    assert "사용자를 확인하지 못했어요" in call(signed_event(payload))[1]["data"]["content"]


# ── 명령어 등록 ────────────────────────────────────────────────
def test_registered_commands_match_handler():
    assert [c["name"] for c in register.COMMANDS] == ["구독", "해지", "목록"]
    for cmd in register.COMMANDS[:2]:
        option = cmd["options"][0]
        assert option["name"] == "키워드" and option["required"] and option["max_length"] == interactions.subscriptions.MAX_LENGTH
    for cmd in register.COMMANDS:   # 디스코드 한도: 설명 100자
        assert len(cmd["description"]) <= 100 and all(len(o["description"]) <= 100 for o in cmd.get("options", []))


def test_register_calls_discord():
    class Session:
        def put(self, url, json, timeout, headers):
            self.call = (url, json, headers["Authorization"])
            return type("Res", (), {"status_code": 200, "text": "", "json": lambda self: json})()

    session = Session()
    assert register.register("tok", "42", session=session) == register.COMMANDS
    assert session.call == ("https://discord.com/api/v10/applications/42/commands", register.COMMANDS, "Bot tok")
    register.register("tok", "42", guild_id="7", session=session)
    assert session.call[0].endswith("/applications/42/guilds/7/commands")
