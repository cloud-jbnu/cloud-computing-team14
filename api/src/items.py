"""GET /items — 웹(web/js/api.js)이 호출하는 목록 API.

응답 형식은 docs/api.md 참고: {"items": [Item, ...]}
쿼리: ?category=univ|contest|jobs|tech (없으면 전체)

전체 목록도 카테고리마다 최신 LIMIT건씩 가져와 합칩니다. 전체에서 최신 LIMIT건만 자르면
글이 많이 올라오는 카테고리(테크 트렌드)에 밀려, 마감이 몇 주 남은 채용·대회 글도 며칠 만에 목록에서 사라집니다.
"""
import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE = boto3.resource("dynamodb").Table(os.environ["ITEMS_TABLE"])
CATEGORIES = ("univ", "contest", "jobs", "tech")
LIMIT = 200  # 카테고리마다 돌려줄 최신 글 수 (전체 목록은 최대 LIMIT × 4건)


def _json_default(o):
    if isinstance(o, Decimal):
        return int(o) if o % 1 == 0 else float(o)
    raise TypeError(f"직렬화할 수 없는 값: {type(o)}")


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False, default=_json_default),
    }


def latest_in(category):
    """한 카테고리의 최신 LIMIT건."""
    res = TABLE.query(
        IndexName="category-date-index",
        KeyConditionExpression=Key("category").eq(category),
        ScanIndexForward=False,  # 최신순
        Limit=LIMIT,
    )
    return res["Items"]


def list_items(category=None):
    """category를 주면 그 카테고리만, 없으면 모든 카테고리를 합쳐 최신순으로 돌려줍니다."""
    items = [it for c in ([category] if category else CATEGORIES) for it in latest_in(c)]
    items.sort(key=lambda it: it.get("date", ""), reverse=True)
    return items


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    category = params.get("category")
    if category and category not in CATEGORIES:
        return _response(400, {"message": "category는 univ, contest, jobs, tech 중 하나여야 해요."})
    try:
        return _response(200, {"items": list_items(category)})
    except Exception as e:
        print(f"목록 조회 실패: {e}")
        return _response(500, {"message": "목록을 불러오지 못했어요."})
