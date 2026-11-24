"""디스코드 명령어(/구독, /해지, /목록)를 받는 Lambda — Interactions Endpoint.

사용자가 명령어를 쓰면 디스코드가 이 주소로 POST를 보내고, 3초 안에 돌려준 답이 그대로 답장이 됩니다.
봇 프로그램(bot.py)을 계속 켜 둘 필요가 없습니다.

  1. 서명 검사   디스코드가 보낸 요청인지 확인합니다 (헤더의 Ed25519 서명 ↔ 앱의 Public Key).
                 틀리면 401. 디스코드는 주소를 등록할 때 일부러 틀린 서명도 보내 보고, 401이 아니면 등록을 거부합니다.
  2. PING        등록 확인용 요청 → PONG
  3. 명령어      subscriptions.reply()로 처리해 본인에게만 보이는 답장으로 돌려줍니다.
  4. 자동 완성   /해지에서 키워드를 입력할 때 내 구독 목록을 선택지로 돌려줍니다.

환경변수: DISCORD_PUBLIC_KEY (개발자 포털 → General Information → Public Key), SUBSCRIPTIONS_TABLE
"""
import base64
import json
import os

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

import subscriptions

# 디스코드 Interaction 종류와 답 종류
PING, COMMAND, AUTOCOMPLETE = 1, 2, 4
PONG, MESSAGE, CHOICES = 1, 4, 8
EPHEMERAL = 64  # 명령어를 쓴 사람에게만 보이는 답장

_table = None


def table():
    global _table
    if _table is None:
        import boto3
        _table = boto3.resource("dynamodb").Table(os.environ["SUBSCRIPTIONS_TABLE"])
    return _table


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def verify(public_key, signature, timestamp, body):
    """디스코드 서명이 맞으면 True. body는 받은 그대로의 bytes여야 합니다 (다시 직렬화하면 서명이 안 맞음)."""
    try:
        VerifyKey(bytes.fromhex(public_key)).verify(timestamp.encode("utf-8") + body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError, TypeError):  # 서명 틀림, 16진수가 아님, 길이가 안 맞음
        return False


def user_id_of(interaction):
    """명령어를 쓴 사람의 디스코드 ID. 서버에서는 member.user, DM에서는 user에 들어 있습니다."""
    user = (interaction.get("member") or {}).get("user") or interaction.get("user") or {}
    user_id = str(user.get("id") or "")
    return user_id if user_id.isdigit() else None


def _message(text):
    return {"type": MESSAGE, "data": {"content": text, "flags": EPHEMERAL, "allowed_mentions": {"parse": []}}}


def handle(interaction, subs_table):
    """검사를 통과한 Interaction 하나 → 디스코드에 돌려줄 답."""
    kind = interaction.get("type")
    if kind == PING:
        return {"type": PONG}

    data = interaction.get("data") or {}
    options = {o.get("name"): o for o in data.get("options") or [] if isinstance(o, dict)}
    keyword = (options.get("키워드") or {}).get("value")
    user_id = user_id_of(interaction)

    if kind == AUTOCOMPLETE:
        try:
            choices = subscriptions.suggest(subs_table, user_id, str(keyword or "")) if user_id else []
        except Exception as e:  # 선택지를 못 만들어도 직접 입력하면 되므로 빈 목록
            print(f"자동 완성 실패: {e}")
            choices = []
        return {"type": CHOICES, "data": {"choices": [{"name": k, "value": k} for k in choices]}}

    if kind != COMMAND:
        return _message("지원하지 않는 요청이에요.")
    if not user_id:
        return _message("사용자를 확인하지 못했어요. 잠시 뒤 다시 해 주세요.")
    try:
        return _message(subscriptions.reply(subs_table, data.get("name"), user_id, keyword))
    except Exception as e:
        print(f"명령어 처리 실패 ({data.get('name')}): {e}")
        return _message("구독 정보를 처리하지 못했어요. 잠시 뒤 다시 해 주세요.")


def lambda_handler(event, context):
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    raw = event.get("body") or ""
    body = base64.b64decode(raw) if event.get("isBase64Encoded") else raw.encode("utf-8")

    public_key = os.environ.get("DISCORD_PUBLIC_KEY", "")
    if not public_key:
        print("DISCORD_PUBLIC_KEY가 없어 모든 요청을 거부함 (배포할 때 DiscordPublicKey를 넘겨 주세요)")
    signature, timestamp = headers.get("x-signature-ed25519"), headers.get("x-signature-timestamp")
    if not (public_key and signature and timestamp and verify(public_key, signature, timestamp, body)):
        return _response(401, {"message": "invalid request signature"})

    try:
        interaction = json.loads(body)
    except ValueError:
        interaction = None
    if not isinstance(interaction, dict):
        return _response(400, {"message": "invalid body"})
    # PING은 DB 없이 답합니다 (테이블 설정이 잘못돼도 주소 등록은 되게)
    return _response(200, handle(interaction, None if interaction.get("type") == PING else table()))
