"""/me/subscriptions — 로그인한 사용자의 키워드 구독.

API Gateway(JWT Authorizer)가 Cognito 토큰을 먼저 검사하므로, 여기까지 온 요청은 로그인된 요청입니다.
사용자 ID는 디스코드 사용자 ID를 그대로 써서 봇(/구독, /해지, /목록)과 같은 목록을 봅니다.

  GET    /me/subscriptions              → {"userId": "...", "keywords": [...]}
  PUT    /me/subscriptions  {"keyword"} → 추가 후 전체 목록
  DELETE /me/subscriptions?keyword=...  → 삭제 후 전체 목록
"""
import base64
import json
import os

import boto3
from boto3.dynamodb.conditions import Key

TABLE = boto3.resource("dynamodb").Table(os.environ["SUBSCRIPTIONS_TABLE"])
MAX_KEYWORDS = 20
MAX_LENGTH = 30


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def discord_id(event):
    """Cognito는 디스코드로 로그인한 사용자 이름을 "discord_<디스코드 ID>"로 만듭니다."""
    try:
        username = event["requestContext"]["authorizer"]["jwt"]["claims"]["username"]
    except (KeyError, TypeError):
        return None
    provider, _, user_id = str(username).partition("_")
    return user_id if provider.lower() == "discord" and user_id else None


def clean_keyword(raw):
    """앞뒤·중복 공백을 정리합니다. 쓸 수 없는 값이면 None."""
    if not isinstance(raw, str):
        return None
    keyword = " ".join(raw.split())
    return keyword if 0 < len(keyword) <= MAX_LENGTH else None


def list_keywords(user_id):
    res = TABLE.query(KeyConditionExpression=Key("userId").eq(user_id))
    return sorted(item["keyword"] for item in res["Items"])


def _body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def lambda_handler(event, context):
    user_id = discord_id(event)
    if not user_id:
        return _response(403, {"message": "디스코드로 로그인한 계정만 쓸 수 있어요."})

    method = event.get("requestContext", {}).get("http", {}).get("method")
    try:
        if method == "PUT":
            try:
                keyword = clean_keyword(_body(event).get("keyword"))
            except ValueError:
                keyword = None
            if not keyword:
                return _response(400, {"message": f"키워드는 1~{MAX_LENGTH}자로 적어 주세요."})
            keywords = list_keywords(user_id)
            if keyword not in keywords:
                if len(keywords) >= MAX_KEYWORDS:
                    return _response(400, {"message": f"키워드는 {MAX_KEYWORDS}개까지 구독할 수 있어요."})
                TABLE.put_item(Item={"userId": user_id, "keyword": keyword})

        elif method == "DELETE":
            keyword = clean_keyword((event.get("queryStringParameters") or {}).get("keyword"))
            if not keyword:
                return _response(400, {"message": "지울 키워드를 keyword로 넘겨 주세요."})
            TABLE.delete_item(Key={"userId": user_id, "keyword": keyword})

        elif method != "GET":
            return _response(405, {"message": "지원하지 않는 요청이에요."})

        return _response(200, {"userId": user_id, "keywords": list_keywords(user_id)})
    except Exception as e:
        print(f"구독 처리 실패: {e}")
        return _response(500, {"message": "구독 정보를 처리하지 못했어요."})
