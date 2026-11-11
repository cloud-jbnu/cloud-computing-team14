"""수집기 예시. 실제 사이트를 붙일 때 이 파일을 복사해서 시작하세요.

fetch()는 docs/api.md의 Item 형식 딕셔너리 목록을 돌려줘야 합니다.
"""


def fetch():
    # 실제 구현 예:
    #   html = requests.get(URL, timeout=10).text
    #   soup = BeautifulSoup(html, "html.parser")
    #   for row in soup.select("table.board tr"): ...
    return [
        {
            "id": "example-univ-0001",
            "category": "univ",
            "subtype": "예시대",
            "source": "예시대 컴퓨터공학과",
            "title": "수집기 동작 확인용 예시 공지",
            "fields": ["backend"],
            "date": "2026-11-11",
            "url": "https://example.com/notice/1",
        }
    ]
