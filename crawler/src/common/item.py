"""수집기가 Item(docs/api.md)을 만들 때 쓰는 도우미.

- make_id / hash_id: 같은 글이면 매번 같은 id가 나오게 합니다 (중복 제거의 기준).
- parse_date: 사이트마다 다른 날짜 표기를 YYYY-MM-DD로 맞춥니다.
"""
import hashlib
import re
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


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
