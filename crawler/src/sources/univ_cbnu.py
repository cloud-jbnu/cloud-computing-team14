"""충북대학교 공지사항 (학교 전체 공지).

https://www.chungbuk.ac.kr/www/selectBbsNttList.do?bbsNo=8&key=813  — robots.txt 없음
표의 칸 순서: 번호 · 분류 · 제목 · 첨부 · 작성 부서 · 날짜 · 조회수
"""
import re

from common import board, http

SCHOOL = "충북대"
LIST_URL = "https://www.chungbuk.ac.kr/www/selectBbsNttList.do?bbsNo=8&key=813"
VIEW_URL = "https://www.chungbuk.ac.kr/www/selectBbsNttView.do?key=813&bbsNo=8&nttNo={number}"

_NUMBER = re.compile(r"[?&]nttNo=(\d+)")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse(html):
    items = []
    for row in board.soup_of(html).select("table tbody tr"):
        link = row.select_one("td.p-subject a[href]")
        number = _NUMBER.search(link["href"]) if link else None
        if not number:
            continue
        cells = row.find_all("td")
        date_index = next((i for i, td in enumerate(cells) if _DATE.fullmatch(board.text_of(td))), None)
        if date_index is None:
            continue
        it = board.notice(
            "cbnu", SCHOOL, number[1],
            title=board.text_of(link),
            writer=board.text_of(cells[date_index - 1]),   # 날짜 바로 앞 칸이 작성 부서
            date_text=board.text_of(cells[date_index]),
            url=VIEW_URL.format(number=number[1]),
        )
        if it:
            items.append(it)
    return items


def fetch():
    return parse(http.get_html(LIST_URL))


def fetch_body(it):
    return board.body_text(http.get_html(it["url"]), ".contenttext")
