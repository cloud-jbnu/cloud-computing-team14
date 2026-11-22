"""부산대학교 공지사항 (학교 전체 공지).

https://www.pusan.ac.kr/kor/CMS/Board/Board.do?mCode=MN095  — robots.txt 없음
상단 고정 공지는 제목이 "…"로 잘려 나오는데, 첨부파일 아이콘의 설명에 전체 제목이 있으면 그것을 씁니다.
"""
import re

from common import board, http

SCHOOL = "부산대"
LIST_URL = "https://www.pusan.ac.kr/kor/CMS/Board/Board.do?mCode=MN095"
VIEW_URL = "https://www.pusan.ac.kr/kor/CMS/Board/Board.do?mCode=MN095&mode=view&mgr_seq=3&board_seq={number}"

_NUMBER = re.compile(r"[?&]board_seq=(\d+)")
_FULL_TITLE = re.compile(r"^'(.+)'의 첨부파일$")


def _title(row, link):
    title = board.text_of(link)
    if title.endswith("..."):
        icon = row.select_one("img.isFileIcon[alt]")
        full = _FULL_TITLE.match(icon["alt"].strip()) if icon else None
        if full:
            return full[1]
    return title


def parse(html):
    items = []
    for row in board.soup_of(html).select("table tbody tr"):
        link = row.select_one("td.subject a[href]")
        number = _NUMBER.search(link["href"]) if link else None
        if not number:
            continue
        it = board.notice(
            "pnu", SCHOOL, number[1],
            title=_title(row, link),
            writer=board.text_of(row.select_one("td.writer")),
            date_text=board.text_of(row.select_one("td.date")),
            url=VIEW_URL.format(number=number[1]),
        )
        if it:
            items.append(it)
    return items


def fetch():
    return parse(http.get_html(LIST_URL))


def fetch_body(it):
    return board.body_text(http.get_html(it["url"]), ".board-view-cont")
