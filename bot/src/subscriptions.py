"""키워드 구독 — 봇 명령어(/구독, /해지, /목록)가 쓰는 저장·응답 로직.

웹(api/src/me.py)과 같은 DynamoDB 테이블(SUBSCRIPTIONS_TABLE)을 같은 규칙으로 씁니다.
그래서 디스코드에서 넣은 구독이 웹에 보이고, 웹에서 넣은 구독이 /목록에 보이며,
크롤러(crawler/src/notify.py)는 어느 쪽에서 넣었든 같은 목록으로 DM을 보냅니다.

  한 줄 = {"userId": 디스코드 사용자 ID(문자열), "keyword": 키워드}   (docs/api.md의 Subscription)

MAX_KEYWORDS, MAX_LENGTH, clean_keyword는 api/src/me.py와 같아야 합니다.
(Lambda 꾸러미가 달라 코드를 같이 쓰지 못합니다. 다르면 tests/integration이 실패합니다.)
"""
from boto3.dynamodb.conditions import Key

MAX_KEYWORDS = 20
MAX_LENGTH = 30


def clean_keyword(raw):
    """앞뒤·중복 공백을 정리합니다. 쓸 수 없는 값이면 None."""
    if not isinstance(raw, str):
        return None
    keyword = " ".join(raw.split())
    return keyword if 0 < len(keyword) <= MAX_LENGTH else None


# ── 테이블 ─────────────────────────────────────────────────────
def list_keywords(table, user_id):
    res = table.query(KeyConditionExpression=Key("userId").eq(user_id))
    return sorted(row["keyword"] for row in res["Items"])


def add(table, user_id, keyword):
    """구독을 추가합니다. "added" | "exists" | "full" """
    keywords = list_keywords(table, user_id)
    if keyword in keywords:
        return "exists"
    if len(keywords) >= MAX_KEYWORDS:
        return "full"
    table.put_item(Item={"userId": user_id, "keyword": keyword})
    return "added"


def remove(table, user_id, keyword):
    """구독을 지웁니다. 있던 구독이면 True."""
    res = table.delete_item(Key={"userId": user_id, "keyword": keyword}, ReturnValues="ALL_OLD")
    return "Attributes" in res


# ── 명령어 → 답장 ──────────────────────────────────────────────
def _code(keyword):
    """답장에 `키워드`로 보여 줄 때 서식이 깨지지 않게 합니다."""
    return "`" + keyword.replace("`", "'") + "`"


def reply(table, command, user_id, keyword=None):
    """명령어 하나를 처리하고 사용자에게 보여 줄 답장을 돌려줍니다."""
    if command == "목록":
        keywords = list_keywords(table, user_id)
        if not keywords:
            return "구독한 키워드가 없어요. `/구독 해커톤`처럼 추가해 보세요."
        return f"구독 중인 키워드 {len(keywords)}개: " + ", ".join(_code(k) for k in keywords)

    if command not in ("구독", "해지"):
        return "모르는 명령어예요. `/구독`, `/해지`, `/목록`을 쓸 수 있어요."

    keyword = clean_keyword(keyword)
    if not keyword:
        return f"키워드는 1~{MAX_LENGTH}자로 적어 주세요."

    if command == "구독":
        result = add(table, user_id, keyword)
        if result == "full":
            return f"키워드는 {MAX_KEYWORDS}개까지 구독할 수 있어요. `/해지`로 정리한 뒤 다시 해 주세요."
        if result == "exists":
            return f"{_code(keyword)}는 이미 구독 중이에요."
        return f"{_code(keyword)} 구독을 시작했어요. 제목·출처에 이 키워드가 들어간 새 글이 올라오면 DM으로 알려 드릴게요."

    if remove(table, user_id, keyword):
        return f"{_code(keyword)} 구독을 해지했어요."
    return f"{_code(keyword)}는 구독하고 있지 않아요. `/목록`으로 확인해 보세요."


def suggest(table, user_id, typed=""):
    """/해지에서 키워드를 고를 때 보여 줄 내 구독 목록 (입력한 글자가 들어간 것만)."""
    typed = (typed or "").strip().casefold()
    return [k for k in list_keywords(table, user_id) if typed in k.casefold()][:25]  # 디스코드 선택지 한도 25개
