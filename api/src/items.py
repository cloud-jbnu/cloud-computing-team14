"""GET /items — 웹(web/js/api.js)이 호출하는 목록 API.

응답 형식은 docs/api.md 참고: {"items": [Item, ...]}
쿼리: ?category=univ|contest|jobs|tech (없으면 전체)
"""
import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE = boto3.resource("dynamodb").Table(os.environ["ITEMS_TABLE"])
LIMIT = 200


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


def list_items(category=None):
    if category:
        res = TABLE.query(
            IndexName="category-date-index",
            KeyConditionExpression=Key("category").eq(category),
            ScanIndexForward=False,  # 최신순
            Limit=LIMIT,
        )
        return res["Items"]

    # 전체 목록: 데이터가 적을 동안은 scan으로 충분
    items, kwargs = [], {}
    while len(items) < LIMIT:
        res = TABLE.scan(**kwargs)
        items.extend(res["Items"])
        if "LastEvaluatedKey" not in res:
            break
        kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]
    items.sort(key=lambda it: it.get("date", ""), reverse=True)
    return items[:LIMIT]


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    category = params.get("category")
    if category and category not in {"univ", "contest", "jobs", "tech"}:
        return _response(400, {"message": "category는 univ, contest, jobs, tech 중 하나여야 해요."})
    try:
        return _response(200, {"items": list_items(category)})
    except Exception as e:
        print(f"목록 조회 실패: {e}")
        return _response(500, {"message": "목록을 불러오지 못했어요."})
