"""/me/profile — 로그인한 사용자의 "내 학교" 설정. 이메일·디스코드 로그인 모두 씁니다.

  GET /me/profile  → {"school": "전북대" | "other" | null, "requestedSchool": "..." | null}
  PUT /me/profile  {"school": "전북대" | "other" | null, "requestedSchool": "서울대"}  → 저장한 값

- school은 schools.SCHOOLS 중 하나, 목록에 없는 학교면 "other", 고르지 않으면 null입니다.
- "other"일 때 requestedSchool에 다니는 학교 이름을 적을 수 있습니다 (어느 학교 요청이 많은지 보려고).
- 웹은 이 값으로 "대학 소식"을 내 학교 글만 보여 주고, 크롤러(notify.py)는 학교 공지 DM을 내 학교 글로만 보냅니다.
  크롤러가 디스코드 사용자 ID로 찾을 수 있게 디스코드 사용자는 discordId도 같이 저장합니다.

ProfilesTable 한 줄: {userId(Cognito sub), school, requestedSchool?, discordId?, updatedAt}
"""
import base64
import json
import os
from datetime import datetime, timezone

from claims import discord_id, user_sub
from schools import OTHER, SCHOOLS

MAX_REQUEST = 30


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def clean(data):
    """PUT 본문을 검사해 저장할 {"school", "requestedSchool"}로. 쓸 수 없으면 ValueError."""
    school = data.get("school")
    if school is not None and school not in SCHOOLS and school != OTHER:
        raise ValueError(f"school은 {', '.join(SCHOOLS)}, {OTHER}, null 중 하나여야 해요.")
    requested = data.get("requestedSchool")
    if school != OTHER or not isinstance(requested, str):
        requested = None
    else:
        requested = " ".join(requested.split())[:MAX_REQUEST] or None
    return {"school": school, "requestedSchool": requested}


def view(row):
    return {"school": (row or {}).get("school"), "requestedSchool": (row or {}).get("requestedSchool")}


def get_profile(table, uid):
    return table.get_item(Key={"userId": uid}).get("Item")


def save_profile(table, uid, profile, discord=None, now=None):
    """school이 null이면 줄을 지웁니다 (설정 안 함 = 기본 동작)."""
    if profile["school"] is None:
        table.delete_item(Key={"userId": uid})
        return view(None)
    row = {
        "userId": uid,
        "school": profile["school"],
        "updatedAt": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
    }
    if profile["requestedSchool"]:
        row["requestedSchool"] = profile["requestedSchool"]
    if discord:
        row["discordId"] = discord
    table.put_item(Item=row)
    return view(row)


def lambda_handler(event, context):
    uid = user_sub(event)
    if not uid:
        return _response(401, {"message": "로그인이 필요해요."})

    import boto3
    table = boto3.resource("dynamodb").Table(os.environ["PROFILES_TABLE"])
    method = event.get("requestContext", {}).get("http", {}).get("method")
    try:
        if method == "GET":
            return _response(200, view(get_profile(table, uid)))
        if method == "PUT":
            try:
                data = _body(event)
            except ValueError:
                return _response(400, {"message": "요청 형식이 맞지 않아요."})
            try:
                profile = clean(data)
            except ValueError as e:
                return _response(400, {"message": str(e)})
            return _response(200, save_profile(table, uid, profile, discord_id(event)))
        return _response(405, {"message": "지원하지 않는 요청이에요."})
    except Exception as e:
        print(f"프로필 처리 실패: {type(e).__name__}: {e}")
        return _response(500, {"message": "학교 설정을 처리하지 못했어요."})
