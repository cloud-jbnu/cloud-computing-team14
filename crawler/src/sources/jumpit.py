"""점핏 — 개발자 채용 공고 중 신입 지원이 가능한 것만 수집합니다.

점핏 웹이 쓰는 목록 API를 최신순으로 읽습니다 (career=0: 신입).
목록에는 게시일이 없어서 date는 처음 수집한 날로 넣습니다.
요약에 쓸 본문(주요 업무·자격 요건)은 새 글에 한해 fetch_body()가 공고 하나씩 가져옵니다.
"""
from common import http, item

LIST_URL = "https://jumpit-api.saramin.co.kr/api/positions"
DETAIL_URL = "https://jumpit-api.saramin.co.kr/api/position/{id}"
PAGE_URL = "https://jumpit.saramin.co.kr/position/{id}"
# 신입 공고 전체를 끝까지 읽습니다 (2026-11-19 기준 전부 58건, 16건씩 4쪽).
# 최신 몇 쪽만 읽으면 실행 주기를 늘렸을 때 그 사이 공고를 놓칩니다. 이미 저장한 공고는 중복 제거에서 빠집니다.
MAX_PAGES = 10  # 응답이 이상해서 끝나지 않을 때를 대비한 상한

# 점핏 직무 이름에 이 글자가 들어 있으면 → 우리 분야
# 회사가 직무를 여러 개 골라 둬서 부정확합니다. AI 요약에 성공하면 AI 태그로 바뀌고, 실패했을 때만 이 태그가 남습니다.
FIELD_KEYWORDS = [
    ("백엔드", "backend"), ("풀스택", "backend"), ("풀스택", "frontend"), ("프론트엔드", "frontend"),
    ("인공지능", "ai"), ("머신러닝", "ai"), ("빅데이터", "data"), ("데이터", "data"),
    ("devops", "cloud"), ("클라우드", "cloud"), ("네트워크", "network"), ("보안", "security"),
    ("안드로이드", "mobile"), ("ios", "mobile"), ("앱개발", "mobile"),
]


def _fields(job_category):
    lowered = (job_category or "").lower()
    return sorted({field for keyword, field in FIELD_KEYWORDS if keyword in lowered})


def parse(data, today=None):
    today = today or item.today().isoformat()
    items = []
    for p in data.get("result", {}).get("positions", []):
        title = (p.get("title") or "").strip()
        out = {
            "id": item.make_id("jumpit", p["id"]),
            "category": "jobs",
            "subtype": "인턴" if "인턴" in title else "신입",
            "source": (p.get("companyName") or "").strip(),
            "title": title,
            "fields": _fields(p.get("jobCategory")),
            "date": today,
            "url": PAGE_URL.format(id=p["id"]),
            "regions": item.regions_of(p.get("locations")),  # 근무지 "서울 강서구" → "서울"
            "body": "직무: {}\n기술: {}\n근무지: {}".format(
                p.get("jobCategory") or "", ", ".join(p.get("techStacks") or []), ", ".join(p.get("locations") or [])),
        }
        deadline = None if p.get("alwaysOpen") else item.parse_date(p.get("closedAt"))
        if deadline:
            out["deadline"] = deadline
        items.append(out)
    return items


def parse_body(data):
    """공고 상세에서 요약에 쓸 글만 모읍니다."""
    result = data.get("result", {})
    parts = [
        ("회사 소개", result.get("serviceInfo")),
        ("주요 업무", result.get("responsibility")),
        ("자격 요건", result.get("qualifications")),
        ("우대 사항", result.get("preferredRequirements")),
    ]
    return "\n\n".join(f"[{label}]\n{text.strip()}" for label, text in parts if text and text.strip())


def fetch():
    items, page_size = [], None
    for page in range(1, MAX_PAGES + 1):
        data = http.get_json(LIST_URL, params={"sort": "reg_dt", "highlight": "false", "career": 0, "page": page})
        found = parse(data)
        items.extend(found)
        page_size = page_size or len(found)
        if not found or len(found) < page_size:  # 빈 쪽이나 덜 찬 쪽이면 마지막 쪽
            break
    return items


def fetch_body(it):
    number = it["id"].split("-", 1)[1]
    return parse_body(http.get_json(DETAIL_URL.format(id=number)))
