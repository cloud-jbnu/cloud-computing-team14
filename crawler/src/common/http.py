"""수집기 공용 HTTP 요청. 모든 수집기는 requests를 직접 쓰지 말고 여기 함수를 씁니다.

- User-Agent로 어떤 프로젝트의 요청인지 밝힙니다.
- 응답이 늦는 사이트 하나 때문에 Lambda 전체가 멈추지 않도록 timeout을 겁니다.
- 일시적인 오류(5xx, 연결 실패, 시간 초과)는 잠깐 쉬고 다시 시도합니다.
"""
import time

import requests

USER_AGENT = "csradar-crawler/0.1 (university course project)"
TIMEOUT = 10  # 초
RETRIES = 2   # 첫 시도 뒤 추가로 시도하는 횟수

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.8"})


def get(url, **kwargs):
    """GET 요청을 보내고 Response를 돌려줍니다. 4xx/5xx는 예외로 올립니다."""
    kwargs.setdefault("timeout", TIMEOUT)
    last_error = None
    for attempt in range(RETRIES + 1):
        try:
            res = _session.get(url, **kwargs)
            if res.status_code < 500:
                res.raise_for_status()  # 4xx는 다시 해도 같으므로 바로 실패
                return res
            last_error = requests.HTTPError(f"HTTP {res.status_code}: {url}")
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e
        if attempt < RETRIES:
            time.sleep(1 + attempt)
    raise last_error


def get_html(url, **kwargs):
    """HTML 본문을 문자열로 돌려줍니다. 헤더에 인코딩이 없으면 본문에서 추정합니다."""
    res = get(url, **kwargs)
    if "charset" not in res.headers.get("Content-Type", "").lower():
        res.encoding = res.apparent_encoding  # EUC-KR 게시판 한글 깨짐 방지
    return res.text


def get_json(url, **kwargs):
    """JSON 응답을 파이썬 값으로 돌려줍니다."""
    return get(url, **kwargs).json()
