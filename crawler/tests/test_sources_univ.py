"""학교 공지 수집기 테스트. 실제 게시판에서 잘라 둔 조각(tests/fixtures/univ_*)으로 돌립니다."""
import pytest

import handler
from common import board
from sources import univ_cbnu, univ_jbnu, univ_knu, univ_pnu

# (수집기, fixture 이름, 첫 글에서 기대하는 값)
CASES = [
    (univ_jbnu, "jbnu", {
        "id": "jbnu-219859", "subtype": "전북대", "source": "전북대 언어교육부", "date": "2026-11-15",
        "title": "[언어교육부] 12월 외국어 강좌 안내/토익,토익스피킹 시험 할인 안내 (강의계획서 붙임 참조)",
        "url": "https://www.jbnu.ac.kr/web/Board/219859/detailView.do?pageIndex=1&menu=2377",
    }),
    (univ_cbnu, "cbnu", {
        "id": "cbnu-171577", "subtype": "충북대", "source": "충북대 창업지원단", "date": "2026-11-12",
        "title": "[2026 모두의 창업] 리부트(Reboot) 캠프 참여자 모집 안내",
        "url": "https://www.chungbuk.ac.kr/www/selectBbsNttView.do?key=813&bbsNo=8&nttNo=171577",
    }),
    (univ_knu, "knu", {
        "id": "knu-1338783", "subtype": "경북대", "source": "경북대 재무과", "date": "2026-11-16",
        "title": "2026학년도 2학기 재학생 미등록자 및 분할납부 미납자 등록금 납부 안내",
        "url": ("https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action"
                "?bbs_cde=1&btin.bbs_cde=1&btin.doc_no=1338783&btin.appl_no=000000&menu_idx=67"),
    }),
    (univ_pnu, "pnu", {
        "id": "pnu-1512125", "subtype": "부산대", "source": "부산대 학생과", "date": "2026-11-11",
        # 목록에는 "…신입생..."으로 잘려 있지만 첨부파일 아이콘 설명에서 전체 제목을 가져옴
        "title": "[학생과] 2027학년도 지방 국립대학교 전액장학금 안내(★2027학년도 신입생 필독)",
        "url": "https://www.pusan.ac.kr/kor/CMS/Board/Board.do?mCode=MN095&mode=view&mgr_seq=3&board_seq=1512125",
    }),
]


@pytest.mark.parametrize("source, key, expected", CASES, ids=[c[1] for c in CASES])
def test_univ_list(fixture_text, source, key, expected):
    items = source.parse(fixture_text(f"univ_{key}_list.html"))
    assert len(items) == 3
    cleaned, invalid = handler.validate(items)
    assert invalid == 0 and len({it["id"] for it in cleaned}) == 3
    assert all(it["category"] == "univ" and it["fields"] == [] for it in items)
    assert {k: items[0][k] for k in expected} == expected


BODY_SELECTORS = {"cbnu": ".contenttext", "knu": "#viewcontent", "pnu": ".board-view-cont"}


@pytest.mark.parametrize("key, start", [
    ("cbnu", "2026학년도 동기 계절수업 1차 등록금 납부 결과에 따른"),
    ("knu", "다양한 융합전공에 대한 정보제공과"),
    ("pnu", "부산대학교 대학일자리플러스센터에서는"),
])
def test_univ_body(fixture_text, key, start):
    body = board.body_text(fixture_text(f"univ_{key}_detail.html"), BODY_SELECTORS[key])
    assert body.startswith(start)
    assert "본문 밖" not in body
    assert not any(tag in body for tag in ("<p", "<div", "<span", "<td", "<br"))   # 태그는 남지 않음
    assert len(body) <= board.MAX_BODY


def test_univ_body_image_only_post_is_empty(fixture_text):
    """전북대 fixture는 본문이 이미지 한 장뿐인 공지."""
    assert board.body_text(fixture_text("univ_jbnu_detail.html"), ".com-post-content-01") == ""


def test_body_text_line_breaks_follow_blocks_not_spans():
    html = '<div class="c"><p>접수 <span>11</span><span>. 18.</span>(수)<br>장소: <b>본관</b></p><table><tr><td>구분</td><td>기간</td></tr></table></div>'
    assert board.body_text(html, ".c") == "접수 11. 18.(수)\n장소: 본관\n구분 기간"


def test_body_text_missing_selector():
    assert board.body_text("<div>글</div>", ".없는영역") == ""


def test_notice_needs_title_and_date():
    assert board.notice("jbnu", "전북대", "1", "제목", "부서", "날짜 없음", "https://example.com") is None
    assert board.notice("jbnu", "전북대", "1", "  ", "부서", "2026-11-17", "https://example.com") is None
    assert board.notice("jbnu", "전북대", "1", "제목", "", "2026-11-17", "https://example.com")["source"] == "전북대"
