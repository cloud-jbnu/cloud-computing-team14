"""학교 공지 게시판 수집기들이 함께 쓰는 도우미.

게시판마다 HTML은 다르지만 "표의 한 줄 = 글 하나"인 점은 같아서,
각 수집기는 줄에서 글 번호·제목·작성 부서·날짜만 뽑아 notice()에 넘깁니다.
"""
import re

from bs4 import BeautifulSoup

from common import item

MAX_BODY = 6000  # 요약에 넘길 본문 글자 수 한도
_BLOCK_TAGS = ["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "dd", "dt"]


def soup_of(html):
    return BeautifulSoup(html, "html.parser")


def text_of(node):
    """태그 안의 글자를 공백 하나로 이어서 돌려줍니다. 태그가 없으면 ""."""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def notice(prefix, school, number, title, writer, date_text, url):
    """학교 공지 Item 하나를 만듭니다. 제목이나 날짜를 읽지 못하면 None."""
    title = re.sub(r"\s+", " ", title or "").strip()
    date = item.parse_date(date_text)
    if not (number and title and date):
        return None
    writer = re.sub(r"\s+", " ", writer or "").strip()
    return {
        "id": item.make_id(prefix, number),
        "category": "univ",
        "subtype": school,
        "source": f"{school} {writer}".strip(),
        "title": title,
        "fields": [],
        "date": date,
        "url": url,
    }


def body_text(html, selector):
    """글 본문 페이지에서 selector에 해당하는 부분의 글자만 뽑습니다.

    본문이 이미지뿐인 공지는 ""가 나옵니다 (그때는 제목만으로 요약합니다).
    """
    soup = soup_of(html)
    for tag in soup.select("script, style"):
        tag.decompose()
    node = soup.select_one(selector)
    if not node:
        return ""
    # 문단·줄·표의 줄이 끝나는 곳에서만 줄을 바꾸고, 글자 꾸밈용 태그(span, b 등)에서는 바꾸지 않습니다.
    for tag in node.find_all("br"):
        tag.replace_with("\n")
    for tag in node.find_all(_BLOCK_TAGS):
        tag.append("\n")
    for tag in node.find_all(["td", "th"]):
        tag.append(" ")
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in node.get_text("").splitlines()]
    return "\n".join(line for line in lines if line)[:MAX_BODY]
