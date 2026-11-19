"""GeekNews — 국내 개발자 뉴스. 사이트가 제공하는 RSS(Atom) 피드를 읽습니다.

https://news.hada.io/rss/news
피드에 글 요약이 들어 있어 본문 페이지를 따로 요청하지 않습니다.
"""
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from common import http, item

URL = "https://news.hada.io/rss/news"
ATOM = "{http://www.w3.org/2005/Atom}"


def parse(xml):
    items = []
    for entry in ET.fromstring(xml).iter(f"{ATOM}entry"):
        url = (entry.findtext(f"{ATOM}id") or "").strip()      # utm 파라미터가 없는 주소
        topic = re.search(r"[?&]id=(\d+)", url)
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        date = item.parse_date(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated"))
        if not (topic and title and date):
            continue
        content = entry.findtext(f"{ATOM}content") or ""
        items.append({
            "id": item.make_id("geeknews", topic[1]),
            "category": "tech",
            "subtype": "최신기술",
            "source": "GeekNews",
            "title": title,
            "fields": [],
            "date": date,
            "url": url,
            "body": BeautifulSoup(content, "html.parser").get_text("\n", strip=True),
        })
    return items


def fetch():
    return parse(http.get(URL).content)
