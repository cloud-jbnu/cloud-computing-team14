"""경북대학교 공지사항 (학교 전체 공지).

https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67  — robots.txt 없음
"""
import re

from common import board, http

SCHOOL = "경북대"
LIST_URL = "https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/list.action?bbs_cde=1&menu_idx=67"
VIEW_URL = ("https://www.knu.ac.kr/wbbs/wbbs/bbs/btin/viewBtin.action"
            "?bbs_cde=1&btin.bbs_cde=1&btin.doc_no={number}&btin.appl_no={appl}&menu_idx=67")

_NUMBER = re.compile(r"btin\.doc_no=(\d+)")
_APPL = re.compile(r"btin\.appl_no=(\d+)")


def parse(html):
    items = []
    for row in board.soup_of(html).select("table tbody tr"):
        link = row.select_one("td.subject a[href]")
        number = _NUMBER.search(link["href"]) if link else None
        if not number:
            continue
        appl = _APPL.search(link["href"])
        it = board.notice(
            "knu", SCHOOL, number[1],
            title=board.text_of(link),
            writer=board.text_of(row.select_one("td.writer")),
            date_text=board.text_of(row.select_one("td.date")),   # "2026/11/16"
            url=VIEW_URL.format(number=number[1], appl=appl[1] if appl else "000000"),
        )
        if it:
            items.append(it)
    return items


def fetch():
    return parse(http.get_html(LIST_URL))


def fetch_body(it):
    return board.body_text(http.get_html(it["url"]), "#viewcontent")
