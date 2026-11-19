"""Lambda 진입점. EventBridge가 주기적으로 호출합니다.

  1. collect   각 수집기(sources/*.py)의 fetch()를 돌려 Item 목록을 모읍니다.
  2. find_new  형식 검사 → 중복 제거(dedupe.py)를 거쳐 처음 보는 글만 남깁니다.
     backlog   처음 수집하는 사이트의 밀린 글을 골라 둡니다. 저장은 하되 6·7번에서 뺍니다 (backlog.py).
  3. cap      새 글이 너무 많으면 최신 글부터 일부만 처리하고 나머지는 다음 실행으로 미룹니다.
  4. summarize 새 글의 본문을 가져와 AI로 요약합니다 (summarize.py).
  5. save      새 글을 DynamoDB(ITEMS_TABLE)에 저장하고, 중복 비교용 키를 SEEN_TABLE에 적습니다.
  6. post      새 글을 디스코드 서버 채널에 요약과 함께 올립니다 (channels.py).
  7. notify    새 글을 키워드 구독자에게 디스코드 DM으로 알립니다 (notify.py).

로컬에서 `python src/handler.py`로 실행하면 저장하지 않고 새 글로 판단한 결과만 출력합니다.
"""
import json
import os
import re
import time

import backlog
import channels
import dedupe
import notify
import summarize
from common.item import CATEGORIES, FIELDS
from sources import dev_event, geeknews, github_trending, jumpit, univ_cbnu, univ_jbnu, univ_knu, univ_pnu

# 수집기 등록 — 새 사이트를 만들면 여기에 추가.
# 다른 사이트에 같은 글이 있으면 여기서 먼저 나온 사이트의 글만 남습니다 (dedupe.cross_site).
SOURCES = [
    univ_jbnu,
    univ_cbnu,
    univ_knu,
    univ_pnu,
    jumpit,
    dev_event,
    geeknews,
    github_trending,
]

MAX_NEW_PER_RUN = 30   # 한 번 실행에서 요약·저장할 새 글 수
BODY_PAUSE = 0.5       # 본문 페이지 요청 사이에 쉬는 시간(초)

# docs/api.md의 Item 형식 (category·fields 값은 common/item.py)
REQUIRED_TEXT = ("id", "subtype", "source", "title", "url")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def collect():
    items = []
    for source in SOURCES:
        try:
            fetched = source.fetch()
        except Exception as e:  # 한 사이트가 실패해도 나머지는 계속
            print(f"[{source.__name__}] 수집 실패: {e}")
            continue
        for it in fetched:
            if isinstance(it, dict):
                it["_module"] = source  # 나중에 본문을 가져올 수집기 (저장되지 않음)
        items.extend(fetched)
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


def validate(raw_items):
    """형식이 맞는 글만 정리해서 돌려줍니다. (글 목록, 형식 오류 개수)"""
    items, invalid = [], 0
    for raw in raw_items:
        try:
            item, reason = clean(raw)
        except (TypeError, ValueError) as e:  # 예: starsToday가 숫자가 아님
            item, reason = None, str(e)
        if item is None:
            invalid += 1
            print(f"형식 오류로 건너뜀 ({reason}): {raw!r:.200}")
        else:
            items.append(item)
    return items, invalid


def find_new(raw_items, items_table=None, seen_table=None):
    """처음 보는 글만 남깁니다. (새 글 목록, 단계별 개수)

    테이블을 주지 않으면(로컬 실행) 이번에 모은 글끼리만 비교합니다.
    """
    stats = {"collected": len(raw_items)}
    items, stats["invalid"] = validate(raw_items)
    items, stats["dupInRun"] = dedupe.in_run(items)

    stats["existing"] = 0
    if items_table is not None:
        known = dedupe.existing_ids(items_table, items)
        stats["existing"] = len(known)
        items = [it for it in items if it["id"] not in known]

    items, stats["dupCrossSite"] = dedupe.cross_site(items, seen_table)
    stats["new"] = len(items)
    print(
        f"수집 {stats['collected']}건 → 형식 오류 {stats['invalid']}, 실행 내 중복 {stats['dupInRun']}, "
        f"이미 있음 {stats['existing']}, 사이트 간 중복 {stats['dupCrossSite']}, 새 글 {stats['new']}"
    )
    return items, stats


def cap(items, limit=None):
    """한 번에 처리할 새 글 수를 제한합니다. (이번에 처리할 글, 다음으로 미룬 개수)

    처음 배포했을 때처럼 새 글이 한꺼번에 많이 들어오면 본문 요청과 요약 호출이 몰리므로
    최신 글부터 limit건만 처리합니다. 미룬 글은 저장하지 않으므로 다음 실행에서 다시 새 글로 잡힙니다.
    """
    limit = MAX_NEW_PER_RUN if limit is None else limit
    ordered = sorted(items, key=lambda it: it["date"], reverse=True)  # 날짜가 같으면 수집한 순서 유지
    return ordered[:limit], max(0, len(ordered) - limit)


def load_bodies(items, raw_items, pause=BODY_PAUSE):
    """요약에 쓸 본문을 모읍니다. {글 id: 본문}

    목록에서 이미 얻은 내용(raw의 "body")에, 수집기에 fetch_body()가 있으면 본문 페이지 내용을 더합니다.
    본문을 못 가져와도 제목만으로 요약할 수 있으므로 실패는 로그만 남깁니다.
    """
    raw_by_id = {}
    for raw in raw_items:
        if isinstance(raw, dict) and isinstance(raw.get("id"), str):
            raw_by_id.setdefault(raw["id"].strip(), raw)

    bodies = {}
    for item in items:
        raw = raw_by_id.get(item["id"], {})
        parts = [raw["body"]] if isinstance(raw.get("body"), str) and raw["body"].strip() else []
        fetch_body = getattr(raw.get("_module"), "fetch_body", None)
        if fetch_body:
            try:
                detail = fetch_body(item)
                if detail:
                    parts.append(detail)
            except Exception as e:
                print(f"본문 가져오기 실패 [{item['id']}]: {e}")
            time.sleep(pause)  # 같은 사이트에 연달아 요청하지 않게
        bodies[item["id"]] = "\n\n".join(parts)
    return bodies


def add_summaries(items, raw_items):
    """새 글에 AI 요약을 붙입니다. 실패하면 요약 없이 그대로 둡니다 (수집·저장은 계속)."""
    try:
        results = summarize.summarize(items, load_bodies(items, raw_items))
        summarize.apply(items, results)
        return sum(1 for r in results.values() if r["summary"])
    except Exception as e:
        print(f"요약 실패: {e}")
        return 0


def save(items, table):
    """새 글을 저장하고 실제로 저장된 글 목록을 돌려줍니다.

    find_new가 이미 걸렀지만, 그 사이 다른 실행이 같은 글을 넣었을 수 있어
    같은 id가 있으면 덮어쓰지 않고 건너뜁니다.
    """
    errors = table.meta.client.exceptions
    saved = []
    for item in items:
        try:
            table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
            saved.append(item)
        except errors.ConditionalCheckFailedException:
            pass
    print(f"저장 {len(saved)}건")
    return saved


def find_quiet(new_items, seen_table):
    """게시·알림하지 않을 글의 id 집합 (backlog.py). 확인에 실패하면 이번 실행은 아무것도 알리지 않습니다.

    밀린 글을 알리지 못하는 것보다 수십 건을 한꺼번에 잘못 알리는 쪽이 더 나쁘기 때문입니다.
    """
    try:
        return backlog.quiet_ids(seen_table, new_items)
    except Exception as e:
        print(f"밀린 글 확인 실패, 이번 실행은 저장만 함: {e}")
        return {it["id"] for it in new_items}


def to_announce(saved, quiet):
    """저장한 글 중 채널 게시·DM 알림을 보낼 글."""
    return [it for it in saved if it["id"] not in quiet]


def lambda_handler(event, context):
    import boto3  # Lambda에만 필요하므로 로컬 실행 때는 불러오지 않음
    db = boto3.resource("dynamodb")
    items_table = db.Table(os.environ["ITEMS_TABLE"])
    seen_table = db.Table(os.environ["SEEN_TABLE"])

    raw_items = collect()
    new_items, stats = find_new(raw_items, items_table, seen_table)
    quiet = find_quiet(new_items, seen_table)   # 상한으로 미룰 글까지 적어야 하므로 cap보다 먼저
    new_items, stats["deferred"] = cap(new_items)
    if stats["deferred"]:
        print(f"새 글이 많아 {len(new_items)}건만 처리하고 {stats['deferred']}건은 다음 실행으로 미룸")
    stats["summarized"] = add_summaries(new_items, raw_items)
    saved = save(new_items, items_table)
    stats["saved"] = len(saved)
    try:
        dedupe.record(seen_table, saved)
    except Exception as e:  # 키를 못 적어도 저장은 끝났으므로 계속 (다음에 사이트 간 중복을 못 잡을 수 있음)
        print(f"중복 비교용 키 기록 실패: {e}")
    announce = to_announce(saved, quiet)
    stats["quiet"] = len(saved) - len(announce)
    if stats["quiet"]:
        print(f"밀린 글 {stats['quiet']}건은 저장만 하고 게시·알림하지 않음")
    # 게시·알림이 실패해도 저장은 이미 끝났으므로 실행 자체는 성공으로 둡니다.
    try:
        posted = channels.post(announce)
    except Exception as e:
        print(f"채널 게시 실패: {e}")
        posted = {"error": str(e)}
    try:
        notified = notify.notify(announce)
    except Exception as e:
        print(f"알림 실패: {e}")
        notified = {"error": str(e)}
    return {"statusCode": 200, "body": json.dumps({**stats, "channels": posted, "notify": notified}, ensure_ascii=False)}


if __name__ == "__main__":
    # 로컬 확인용: 저장·알림 없이 결과만 출력합니다.
    #   python src/handler.py        수집 → 중복 제거까지
    #   python src/handler.py 5      최신 5건은 본문을 가져와 요약까지 (.env에 GEMINI_API_KEY 필요)
    import sys

    raw_items = collect()
    new_items, _ = find_new(raw_items)
    if len(sys.argv) > 1:
        from dotenv import load_dotenv
        load_dotenv()
        new_items, _ = cap(new_items, int(sys.argv[1]))
        add_summaries(new_items, raw_items)
    for it in new_items:
        print(json.dumps(it, ensure_ascii=False))
