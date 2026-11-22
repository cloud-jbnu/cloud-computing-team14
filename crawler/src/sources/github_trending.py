"""GitHub Trending — 오늘 별을 많이 받은 저장소.

https://github.com/trending (robots.txt에서 막지 않는 경로)
한 번 저장된 저장소는 id가 같아서 다음 날 또 트렌딩에 올라와도 새 글로 잡히지 않습니다.
"""
import re

from bs4 import BeautifulSoup

from common import http, item

URL = "https://github.com/trending"


def parse(html, today=None):
    today = today or item.today().isoformat()
    items = []
    for row in BeautifulSoup(html, "html.parser").select("article.Box-row"):
        link = row.select_one("h2 a[href]")
        if not link:
            continue
        path = link["href"].strip("/")          # "owner/repo"
        if path.count("/") != 1:
            continue
        owner, repo = path.split("/")
        desc = row.select_one("p")
        lang = row.select_one('[itemprop="programmingLanguage"]')
        stars = re.search(r"([\d,]+)\s+stars?\s+today", row.get_text(" ", strip=True))
        items.append({
            # 사용자 이름에는 "."을 쓸 수 없으므로 "owner.repo"는 저장소마다 고유합니다.
            "id": item.make_id("github", f"{owner}.{repo}"),
            "category": "tech",
            "subtype": "GitHub",
            "source": "GitHub Trending",
            "title": path,
            "fields": [],
            "date": today,
            "url": f"https://github.com/{path}",
            "repo": {
                "lang": lang.get_text(strip=True) if lang else "",
                "starsToday": int(stars[1].replace(",", "")) if stars else 0,
            },
            "body": desc.get_text(" ", strip=True) if desc else "",
        })
    return items


def fetch():
    return parse(http.get_html(URL))
