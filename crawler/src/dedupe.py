"""중복 제거.

같은 글이 두 번 저장·요약·알림되지 않게 세 번 걸러 냅니다.

  1. in_run        같은 실행 안에서 id가 같은 글 (상단 고정 공지가 목록에 또 나오는 경우 등)
  2. existing_ids  이전 실행에서 이미 저장한 글 (ITEMS_TABLE에 같은 id가 있음)
  3. cross_site    다른 사이트에 올라온 같은 내용 (주소나 제목이 같음)

3번은 글마다 "주소 키"와 "제목 키"를 만들어 SEEN_TABLE에 사이트 이름과 함께 적어 두고,
새 글의 키가 다른 사이트 이름으로 이미 있으면 중복으로 봅니다.
같은 사이트 안에서는 제목이 같아도 다른 글로 봅니다 (매주 같은 제목으로 올라오는 공지 때문).
"""
import hashlib
import re
import time
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit

SEEN_TTL_DAYS = 60       # 이 기간이 지나면 키를 지워, 내년의 같은 이름 행사는 새 글로 봅니다
MIN_TITLE_KEY = 8        # 이보다 짧은 제목("공지", "채용")은 우연히 겹치기 쉬워 비교하지 않습니다
BATCH_GET_LIMIT = 100    # DynamoDB BatchGetItem 한 번에 넣을 수 있는 키 개수

_TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|ref|source)$", re.IGNORECASE)
_LEADING_TAG = re.compile(r"^\s*[\[(【<〔][^\])】>〕]{1,20}[\])】>〕]\s*")


# ── 키 만들기 ──────────────────────────────────────────────────
def site_of(item):
    """수집기가 붙인 id 앞부분이 사이트 이름입니다. "jbnu-12345" → "jbnu" """
    return item["id"].split("-", 1)[0]


def url_key(url):
    """같은 글을 가리키는 주소가 같은 값이 되도록 정리합니다.

    http/https, www., 끝의 /, #뒤, utm_* 같은 추적 파라미터를 떼고 나머지 파라미터는 이름순으로 둡니다.
    """
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k))
    return host + path + ("?" + urlencode(query) if query else "")


def title_key(item):
    """제목을 비교용으로 정리합니다. 너무 짧으면 "" (비교하지 않음).

    전각 문자를 반각으로, 대문자를 소문자로 바꾸고, 앞의 [공지] 같은 머리말과 공백·문장부호를 뗍니다.
    채용 공고는 "백엔드 개발자"처럼 회사만 다른 같은 제목이 많아 회사 이름(source)을 붙여 비교합니다.
    """
    text = unicodedata.normalize("NFKC", item["title"])
    while True:
        stripped = _LEADING_TAG.sub("", text, count=1)
        if stripped == text or not stripped.strip():
            break
        text = stripped
    if item.get("category") == "jobs":
        text = f"{item.get('source', '')} {text}"
    key = re.sub(r"[\W_]+", "", text.casefold())
    return key if len(key) >= MIN_TITLE_KEY else ""


def seen_keys(item):
    """SEEN_TABLE에 적을 키 목록. 긴 주소·제목도 일정한 길이가 되도록 해시로 바꿉니다."""
    keys = [("u", url_key(item["url"]))]
    title = title_key(item)
    if title:
        keys.append(("t", title))
    return [f"{kind}#{hashlib.sha1(value.encode('utf-8')).hexdigest()}" for kind, value in keys if value]


# ── 1. 같은 실행 안 ────────────────────────────────────────────
def in_run(items):
    """id가 같은 글은 먼저 나온 것만 남깁니다. (남은 글, 뺀 개수)"""
    seen, unique = set(), []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)
    return unique, len(items) - len(unique)


# ── 2. 이미 저장한 글 ──────────────────────────────────────────
def batch_get(table, key_name, values, attributes):
    """키 여러 개를 한꺼번에 조회합니다. 없는 키는 결과에 없습니다."""
    names = {f"#a{i}": name for i, name in enumerate(attributes)}
    client, rows = table.meta.client, []
    values = list(dict.fromkeys(values))  # 같은 키를 두 번 넣으면 DynamoDB가 오류를 냄
    for start in range(0, len(values), BATCH_GET_LIMIT):
        request = {table.name: {
            "Keys": [{key_name: v} for v in values[start:start + BATCH_GET_LIMIT]],
            "ProjectionExpression": ", ".join(names),
            "ExpressionAttributeNames": names,
        }}
        for attempt in range(5):  # 한 번에 다 못 읽으면 남은 키(UnprocessedKeys)를 다시 요청
            res = client.batch_get_item(RequestItems=request)
            rows.extend(res.get("Responses", {}).get(table.name, []))
            request = res.get("UnprocessedKeys") or {}
            if not request:
                break
            time.sleep(0.2 * (attempt + 1))
        else:
            raise RuntimeError("DynamoDB 조회를 끝내지 못함 (UnprocessedKeys가 계속 남음)")
    return rows


def existing_ids(table, items):
    """items 중 ITEMS_TABLE에 이미 있는 id 집합."""
    rows = batch_get(table, "id", [it["id"] for it in items], ["id"])
    return {row["id"] for row in rows}


# ── 3. 다른 사이트의 같은 글 ───────────────────────────────────
def cross_site(items, seen_table=None):
    """다른 사이트가 먼저 올린 같은 글을 뺍니다. (남은 글, 뺀 개수)

    seen_table이 없으면(로컬 실행) 이번 실행에서 모은 글끼리만 비교합니다.
    """
    keys_of = {item["id"]: seen_keys(item) for item in items}
    owner = {}  # 키 → 그 글을 먼저 올린 사이트
    if seen_table is not None and items:
        all_keys = [k for keys in keys_of.values() for k in keys]
        for row in batch_get(seen_table, "seenKey", all_keys, ["seenKey", "site"]):
            owner[row["seenKey"]] = row["site"]

    kept = []
    for item in items:
        site, keys = site_of(item), keys_of[item["id"]]
        other = next((owner[k] for k in keys if k in owner and owner[k] != site), None)
        if other:
            print(f"사이트 간 중복으로 건너뜀 ({other}에 이미 있음): [{item['id']}] {item['title']:.60}")
            continue
        for k in keys:
            owner.setdefault(k, site)
        kept.append(item)
    return kept, len(items) - len(kept)


def record(seen_table, items, now=None):
    """저장한 글의 키를 SEEN_TABLE에 적습니다. expiresAt이 지나면 DynamoDB가 지웁니다(TTL)."""
    expires = int(now if now is not None else time.time()) + SEEN_TTL_DAYS * 86400
    with seen_table.batch_writer(overwrite_by_pkeys=["seenKey"]) as batch:
        for item in items:
            for key in seen_keys(item):
                batch.put_item(Item={"seenKey": key, "site": site_of(item), "itemId": item["id"], "expiresAt": expires})
