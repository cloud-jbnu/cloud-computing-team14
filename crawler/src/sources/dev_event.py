"""Dev-Event — 개발자 행사 목록 저장소(brave-people/Dev-Event)의 README에서 대회만 고릅니다.

README의 한 항목은 이렇게 생겼습니다.

    ## `26년 11월`
    - __[행사 이름](https://주소)__
      - 분류: `온라인`, `무료`, `대회`, `AI`
      - 주최: 주최 기관
      - 접수: 10. 12(월) ~ 11. 20(금) 17:00      (또는  - 일시: 11. 21(토) 13:00 ~ 11. 21(토) 18:00)

세미나·모임은 빼고 분류에 `대회`가 있는 항목만 수집합니다.
마감일(접수 마지막 날, 접수 기간이 없으면 행사 시작일)이 오늘보다 앞선 대회는 이미 지원할 수 없으므로 뺍니다.
README에는 글 번호와 게시일이 없어서 id는 주소의 해시로, date는 처음 수집한 날로 넣습니다.
"""
import re
from datetime import date

import dedupe
from common import http, item

URL = "https://raw.githubusercontent.com/brave-people/Dev-Event/master/README.md"

_MONTH = re.compile(r"^##\s*`(\d{2})년\s*(\d{1,2})월`")
_ENTRY = re.compile(r"^- __\[(.+)\]\((\S+?)\)__\s*$")
_DETAIL = re.compile(r"^\s+- (분류|주최|접수|일시):\s*(.+)$")
_DAY = re.compile(r"(\d{1,2})\.\s*(\d{1,2})")

CONTEST_TAGS = {"대회", "해커톤", "공모전"}
FIELD_TAGS = {"AI": "ai", "클라우드": "cloud", "보안": "security", "데이터": "data", "모바일": "mobile",
              "프론트엔드": "frontend", "백엔드": "backend", "네트워크": "network"}


def _subtype(title):
    lowered = title.lower()
    if "해커톤" in title or "hackathon" in lowered:
        return "해커톤"
    if "ctf" in lowered:
        return "CTF"
    if "공모전" in title:
        return "공모전"
    return "경진대회"


def _venue(raw_tags):
    """분류 `온라인` / `오프라인(서울 강남구)` / `온오프라인` → ("online"|"offline"|"hybrid"|None, ["서울"])"""
    online = offline = False
    places = []
    for tag in raw_tags:
        name, _, rest = tag.partition("(")
        name = name.replace(" ", "")
        if name in ("온오프라인", "온·오프라인", "온/오프라인"):
            online = offline = True
        elif name == "온라인":
            online = True
        elif name == "오프라인":
            offline = True
        else:
            continue
        if rest:
            places.append(rest.rstrip(")"))
    venue = "hybrid" if online and offline else "offline" if offline else "online" if online else None
    return venue, item.regions_of(places)


def _dates(text, year, month):
    """"10. 12(월) ~ 11. 20(금) 17:00" → ["2026-10-12", "2026-11-20"]. 연도는 제목 줄(## `26년 11월`)에서 가져옵니다."""
    result = []
    for m, d in _DAY.findall(text):
        m, d, y = int(m), int(d), year
        if m - month > 6:      # 1월 목록의 "12. 20" → 작년
            y -= 1
        elif month - m > 6:    # 12월 목록의 "1. 5" → 내년
            y += 1
        try:
            result.append(date(y, m, d).isoformat())
        except ValueError:     # "13. 40" 같은 없는 날짜
            pass
    return result


def _build(entry, today):
    raw_tags = re.findall(r"`([^`]+)`", entry.get("분류", ""))
    tags = [t.split("(")[0].strip() for t in raw_tags]
    if not CONTEST_TAGS & set(tags):
        return None
    venue, regions = _venue(raw_tags)
    out = {
        "id": item.hash_id("devevent", dedupe.url_key(entry["url"])),
        "category": "contest",
        "subtype": _subtype(entry["title"]),
        "source": entry.get("주최") or "Dev-Event",
        "title": entry["title"],
        "fields": sorted({FIELD_TAGS[t] for t in tags if t in FIELD_TAGS}),
        "date": today,
        "url": entry["url"],
        "body": "\n".join(f"{k}: {entry[k]}" for k in ("분류", "주최", "접수", "일시") if entry.get(k)),
    }
    if venue:
        out["venue"] = venue
    if regions:
        out["regions"] = regions
    # 마감일: 접수 기간의 마지막 날. 접수 기간이 없으면 행사 시작일.
    if entry.get("접수"):
        days = _dates(entry["접수"], entry["year"], entry["month"])
        if days:
            out["deadline"] = days[-1]
    elif entry.get("일시"):
        days = _dates(entry["일시"], entry["year"], entry["month"])
        if days:
            out["deadline"] = days[0]
    if out.get("deadline", today) < today:  # 마감이 지남. 마감일 당일은 아직 지원할 수 있으므로 남김
        return None
    return out


def parse(markdown, today=None):
    today = today or item.today().isoformat()
    entries, current, year, month = [], None, None, None
    for line in markdown.splitlines():
        if line.startswith("## "):
            m = _MONTH.match(line)
            year, month = (2000 + int(m[1]), int(m[2])) if m else (None, None)  # 월 목록이 아닌 구역은 건너뜀
            current = None
            continue
        if year is None:
            continue
        m = _ENTRY.match(line)
        if m:
            current = {"title": m[1].strip(), "url": m[2], "year": year, "month": month}
            entries.append(current)
            continue
        m = _DETAIL.match(line)
        if m and current is not None:
            current[m[1]] = m[2].strip()
    return [it for it in (_build(e, today) for e in entries) if it]


def fetch():
    return parse(http.get(URL).content.decode("utf-8"))
