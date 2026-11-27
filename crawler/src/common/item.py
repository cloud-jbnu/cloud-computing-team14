"""수집기가 Item(docs/api.md)을 만들 때 쓰는 도우미.

- make_id / hash_id: 같은 글이면 매번 같은 id가 나오게 합니다 (중복 제거의 기준).
- parse_date: 사이트마다 다른 날짜 표기를 YYYY-MM-DD로 맞춥니다.
"""
import hashlib
import re
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# Item의 category와 fields에 쓸 수 있는 값. 크롤러 안에서는 여기만 고칩니다.
# 웹(web/js/data.js), API(api/src/items.py), 문서(docs/api.md)에도 같은 목록이 있어 함께 고쳐야 하며,
# 어긋나면 tests/test_constants.py가 실패합니다.
CATEGORIES = ["univ", "contest", "jobs", "tech"]
FIELDS = ["backend", "frontend", "ai", "data", "cloud", "network", "security", "mobile"]
# 공지를 모으는 학교 (category가 univ인 글의 subtype). 학교 수집기(sources/univ_*.py)의 SCHOOL과 같아야 하고,
# 웹(web/js/data.js의 SUBTYPES.univ)과 API(api/src/schools.py)에도 같은 목록이 있습니다.
SCHOOLS = ["전북대", "충북대", "경북대", "부산대"]
# Item의 regions(근무지·행사 장소, 시·도)와 venue(대회 진행 방식)에 쓸 수 있는 값. 웹(web/js/data.js)과 docs/api.md에도 있습니다.
REGIONS = ["서울", "경기", "인천", "강원", "대전", "세종", "충북", "충남", "광주", "전북", "전남",
           "대구", "경북", "부산", "울산", "경남", "제주"]
VENUES = ["online", "offline", "hybrid"]

# 시·도를 긴 이름으로 쓴 경우 ("서울특별시", "전북특별자치도", "경상남도"…)
_REGION_ALIASES = [
    ("충청북", "충북"), ("충청남", "충남"), ("전라북", "전북"), ("전라남", "전남"),
    ("경상북", "경북"), ("경상남", "경남"),
]


def region_of(text):
    """"서울 강서구", "경기도 성남시", "전북특별자치도 전주시" → "서울", "경기", "전북". 모르면 None."""
    text = (text or "").strip()
    for long, short in _REGION_ALIASES:
        if text.startswith(long):
            return short
    for region in REGIONS:
        if text.startswith(region):
            return region
    return None


def regions_of(texts):
    """여러 장소에서 시·도만 뽑아 겹치지 않게, 처음 나온 순서대로."""
    out = []
    for text in texts or []:
        region = region_of(text)
        if region and region not in out:
            out.append(region)
    return out


def today():
    return datetime.now(KST).date()


def make_id(prefix, key):
    """사이트의 글 번호로 id를 만듭니다. make_id("jbnu", 12345) → "jbnu-12345" """
    key = re.sub(r"[^0-9A-Za-z._-]+", "-", str(key)).strip("-")
    if not key:
        raise ValueError("id로 쓸 값이 비어 있음")
    return f"{prefix}-{key}"


def hash_id(prefix, text):
    """글 번호가 없는 사이트용. 주소 같은 고정된 문자열의 해시로 id를 만듭니다."""
    digest = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


_FULL = re.compile(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_SHORT_YEAR = re.compile(r"(?<!\d)(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)")
_NO_YEAR = re.compile(r"(?<!\d)(\d{1,2})\s*[.\-/월]\s*(\d{1,2})(?!\d)")


def parse_date(text, base=None):
    """날짜 문자열을 "YYYY-MM-DD"로 바꿉니다. 읽을 수 없으면 None.

    읽는 형식: 2026-11-17, 2026.11.17, 2026/11/17, 2026년 11월 17일, 2026-11-17T09:00:00+09:00,
              26.11.17, 11.17, 11-17, 11월 17일
    연도가 없으면 올해로 보되, 그 날짜가 한 달 넘게 미래면 작년으로 봅니다 (1월에 본 "12.28" 같은 경우).
    """
    if not text:
        return None
    text = str(text).strip()
    base = base or today()

    m = _FULL.search(text)
    if m:
        return _build(int(m[1]), int(m[2]), int(m[3]))
    m = _SHORT_YEAR.search(text)
    if m:
        return _build(2000 + int(m[1]), int(m[2]), int(m[3]))
    m = _NO_YEAR.search(text)
    if m:
        result = _build(base.year, int(m[1]), int(m[2]))
        if result and date.fromisoformat(result) > base + timedelta(days=31):
            result = _build(base.year - 1, int(m[1]), int(m[2]))
        return result
    return None


def _build(year, month, day):
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None
