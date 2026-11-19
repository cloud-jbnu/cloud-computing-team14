"""수집기 파서 테스트. tests/fixtures/ 에 저장해 둔 실제 응답 조각으로 돌립니다 (네트워크 없음)."""
import handler
from sources import dev_event, geeknews, github_trending

TODAY = "2026-11-17"


def assert_valid(items):
    """수집기가 만든 글이 모두 docs/api.md 형식을 통과하는지 확인합니다."""
    cleaned, invalid = handler.validate(items)
    assert invalid == 0
    assert len({it["id"] for it in cleaned}) == len(items), "id가 겹침"
    return cleaned


# ── GitHub Trending ───────────────────────────────────────────
def test_github_trending(fixture_text):
    items = github_trending.parse(fixture_text("github_trending_list.html"), today=TODAY)
    assert_valid(items)
    assert [it["title"] for it in items] == ["ag-ui-protocol/ag-ui", "backnotprop/plannotator", "dream-num/univer"]
    first = items[0]
    assert first["id"] == "github-ag-ui-protocol.ag-ui"
    assert first["url"] == "https://github.com/ag-ui-protocol/ag-ui"
    assert (first["category"], first["subtype"], first["date"]) == ("tech", "GitHub", TODAY)
    assert first["repo"] == {"lang": "TypeScript", "starsToday": 791}
    assert first["body"].startswith("AG-UI: the Agent-User Interaction Protocol")
    assert items[2]["repo"]["starsToday"] == 1828   # "1,828 stars today"


def test_github_trending_without_language_or_description():
    html = '<article class="Box-row"><h2><a href="/someone/some-repo">someone / some-repo</a></h2></article>'
    items = github_trending.parse(html, today=TODAY)
    assert_valid(items)
    assert items[0]["repo"] == {"lang": "", "starsToday": 0} and items[0]["body"] == ""


# ── GeekNews ──────────────────────────────────────────────────
def test_geeknews(fixture_text):
    items = geeknews.parse(fixture_text("geeknews_list.xml"))
    assert_valid(items)
    assert [it["id"] for it in items] == ["geeknews-37336", "geeknews-37333", "geeknews-37332"]
    first = items[0]
    assert first["title"] == "화학은 사실 기하학이다"
    assert first["url"] == "https://news.hada.io/topic?id=37336"   # utm 파라미터 없는 주소
    assert (first["category"], first["subtype"], first["date"]) == ("tech", "최신기술", "2026-11-17")
    assert "화학 반응 네트워크 이론" in first["body"] and "<" not in first["body"]


# ── Dev-Event ─────────────────────────────────────────────────
def test_dev_event_picks_only_contests_in_month_sections(fixture_text):
    items = dev_event.parse(fixture_text("dev_event_list.md"), today=TODAY)
    assert_valid(items)
    assert [it["title"] for it in items] == [
        "2026 대구광역시 기후·환경·탄소중립 공공데이터 AI 활용대회",
        "[예시] 클라우드 보안 해커톤 (11/21)",
        "예시 겨울 알고리즘 대회",
    ]   # 세미나와 "지난 행사 기록"의 대회는 빠짐


def test_dev_event_fields(fixture_text):
    daegu, hackathon, algo = dev_event.parse(fixture_text("dev_event_list.md"), today=TODAY)
    assert daegu["category"] == "contest" and daegu["subtype"] == "경진대회"
    assert daegu["source"] == "대구광역시 탄소중립지원센터"
    assert daegu["url"] == "https://www.dcnc.or.kr/bbs/board.php?bo_table=notice&wr_id=193"
    assert daegu["fields"] == ["ai"]
    assert daegu["date"] == TODAY
    assert daegu["deadline"] == "2026-11-20"          # 접수 마지막 날
    assert "접수: 10. 12(월) ~ 11. 20(금) 17:00" in daegu["body"]

    assert hackathon["subtype"] == "해커톤"
    assert hackathon["fields"] == ["cloud", "security"]
    assert hackathon["deadline"] == "2026-11-21"      # 접수 기간이 없으면 행사 시작일

    assert algo["fields"] == []
    assert algo["deadline"] == "2027-01-08"           # 12월 목록의 "1. 08"은 내년


def test_dev_event_skips_contests_past_deadline(fixture_text):
    items = dev_event.parse(fixture_text("dev_event_list.md"), today="2026-11-21")
    assert [it["deadline"] for it in items] == ["2026-11-21", "2027-01-08"]   # 11-20 마감은 빠지고 마감 당일은 남음


def test_dev_event_id_is_stable(fixture_text):
    a = dev_event.parse(fixture_text("dev_event_list.md"), today="2026-11-17")
    b = dev_event.parse(fixture_text("dev_event_list.md"), today="2026-11-18")
    assert [it["id"] for it in a] == [it["id"] for it in b]
    assert all(it["id"].startswith("devevent-") for it in a)


# ── 점핏 ──────────────────────────────────────────────────────
def test_jumpit(fixture_text):
    import json
    from sources import jumpit

    items = jumpit.parse(json.loads(fixture_text("jumpit_list.json")), today=TODAY)
    assert_valid(items)
    web, sil, hil = items
    assert web["id"] == "jumpit-55592439"
    assert web["url"] == "https://jumpit.saramin.co.kr/position/55592439"
    assert (web["category"], web["subtype"], web["source"]) == ("jobs", "신입", "아이포트폴리오")
    assert web["title"] == "웹 개발자 신입 채용"
    assert web["fields"] == ["backend", "frontend", "mobile", "security"]
    assert web["deadline"] == "2026-12-16"
    assert "React" in web["body"] and "서울 강서구" in web["body"]
    assert sil["fields"] == ["cloud", "data"]
    assert "deadline" not in hil                      # 상시 채용은 마감일 없음


def test_jumpit_body(fixture_text):
    import json
    from sources import jumpit

    body = jumpit.parse_body(json.loads(fixture_text("jumpit_detail.json")))
    assert "[주요 업무]" in body and "[자격 요건]" in body
    assert "휴가" not in body.split("[우대 사항]")[1]    # 복지 안내는 요약에 쓰지 않음
