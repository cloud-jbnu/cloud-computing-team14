"""전북대학교 교내공지 (학교 전체 공지).

https://www.jbnu.ac.kr/web/news/notice/sub01.do  — robots.txt: 전체 허용
제목 링크가 pf_DetailMove('글번호') 자바스크립트 호출이라, 글 번호로 본문 주소를 만듭니다.
"""
import re

from common import board, http

SCHOOL = "전북대"
LIST_URL = "https://www.jbnu.ac.kr/web/news/notice/sub01.do"
VIEW_URL = "https://www.jbnu.ac.kr/web/Board/{number}/detailView.do?pageIndex=1&menu=2377"

_NUMBER = re.compile(r"pf_DetailMove\('(\d+)'\)")


def parse(html):
    items = []
    for row in board.soup_of(html).select("tr.tr-noticed, tr.tr-normal"):   # 상단 고정 공지 + 일반 글
        link = row.select_one("a.title")
        number = _NUMBER.search(link.get("onclick", "")) if link else None
        if not number:
            continue
        it = board.notice(
            "jbnu", SCHOOL, number[1],
            title=board.text_of(link),
            writer=board.text_of(row.select_one(".brd-writer")),
            date_text=board.text_of(row.select_one(".etc-list li")),
            url=VIEW_URL.format(number=number[1]),
        )
        if it:
            items.append(it)
    return items


def fetch():
    return parse(http.get_html(LIST_URL))


def fetch_body(it):
    return board.body_text(http.get_html(it["url"]), ".com-post-content-01")
