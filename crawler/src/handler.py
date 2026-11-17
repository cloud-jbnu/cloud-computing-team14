"""Lambda 진입점. EventBridge가 주기적으로 호출합니다.

각 수집기(sources/*.py)의 fetch()를 돌려 Item 목록을 모은 뒤 DynamoDB(ITEMS_TABLE)에 저장합니다.
이미 저장된 id는 건너뛰고 새 글만 넣습니다.
새로 저장된 글은 notify.py가 키워드 구독자에게 디스코드 DM으로 알립니다.

로컬에서 `python src/handler.py`로 실행하면 저장하지 않고 수집 결과만 출력합니다.
"""
import json
import os
import re

import notify

# 수집기 등록 — 새 사이트를 만들면 여기에 추가
SOURCES = [
]

# docs/api.md의 Item 형식
CATEGORIES = {"univ", "contest", "jobs", "tech"}
FIELDS = {"backend", "frontend", "ai", "data", "cloud", "network", "security", "mobile"}
REQUIRED_TEXT = ("id", "subtype", "source", "title", "url")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def collect():
    items = []
    for source in SOURCES:
        try:
            items.extend(source.fetch())
        except Exception as e:  # 한 사이트가 실패해도 나머지는 계속
            print(f"[{source.__name__}] 수집 실패: {e}")
    return items


def clean(item):
    """Item을 저장할 모양으로 정리합니다. 형식이 틀리면 (None, 이유)를 돌려줍니다."""
    if not isinstance(item, dict):
        return None, "딕셔너리가 아님"
    out = {}
    for key in REQUIRED_TEXT:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            return None, f"{key} 없음"
        out[key] = value.strip()

    if item.get("category") not in CATEGORIES:
        return None, f"category가 잘못됨: {item.get('category')!r}"
    out["category"] = item["category"]

    if not isinstance(item.get("date"), str) or not DATE_RE.match(item["date"]):
        return None, f"date 형식이 잘못됨: {item.get('date')!r}"
    out["date"] = item["date"]

    deadline = item.get("deadline")
    if deadline:
        if not isinstance(deadline, str) or not DATE_RE.match(deadline):
            return None, f"deadline 형식이 잘못됨: {deadline!r}"
        out["deadline"] = deadline

    fields = item.get("fields") or []
    out["fields"] = [f for f in fields if f in FIELDS] if isinstance(fields, list) else []

    repo = item.get("repo")
    if isinstance(repo, dict):
        out["repo"] = {"lang": str(repo.get("lang") or ""), "starsToday": int(repo.get("starsToday") or 0)}

    summary = item.get("summary")
    if isinstance(summary, list) and summary:
        out["summary"] = [str(s) for s in summary]
    return out, None


def save(items, table=None):
    """새 글만 저장하고 ({"saved", "skipped", "invalid"} 개수, 새로 저장한 글 목록)을 돌려줍니다."""
    if table is None:
        import boto3  # Lambda에만 필요하므로 로컬 실행 때는 불러오지 않음
        table = boto3.resource("dynamodb").Table(os.environ["ITEMS_TABLE"])
    errors = table.meta.client.exceptions

    stats = {"saved": 0, "skipped": 0, "invalid": 0}
    new_items = []
    seen = set()
    for raw in items:
        try:
            item, reason = clean(raw)
        except (TypeError, ValueError) as e:  # 예: starsToday가 숫자가 아님
            item, reason = None, str(e)
        if item is None:
            stats["invalid"] += 1
            print(f"형식 오류로 건너뜀 ({reason}): {raw!r:.200}")
            continue
        if item["id"] in seen:  # 같은 실행 안에서 중복
            stats["skipped"] += 1
            continue
        seen.add(item["id"])
        try:
            # 같은 id가 이미 있으면 덮어쓰지 않고 실패하게 해서 새 글만 남깁니다.
            table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
            stats["saved"] += 1
            new_items.append(item)
        except errors.ConditionalCheckFailedException:
            stats["skipped"] += 1
    print(f"수집 {len(items)}건 → 새로 저장 {stats['saved']}, 이미 있음 {stats['skipped']}, 형식 오류 {stats['invalid']}")
    return stats, new_items


def lambda_handler(event, context):
    items = collect()
    stats, new_items = save(items)
    try:
        notified = notify.notify(new_items)
    except Exception as e:  # 알림이 실패해도 저장은 이미 끝났으므로 실행 자체는 성공으로
        print(f"알림 실패: {e}")
        notified = {"error": str(e)}
    return {"statusCode": 200, "body": json.dumps({"collected": len(items), **stats, "notify": notified}, ensure_ascii=False)}


if __name__ == "__main__":
    for it in collect():
        item, reason = clean(it)
        print(item if item else f"형식 오류 ({reason}): {it}")
