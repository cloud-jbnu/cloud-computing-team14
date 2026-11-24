"""새 글 디스코드 DM 알림.

crawler가 새로 저장한 글을 받아, 키워드를 구독한 사용자에게 DM을 보냅니다.
봇이 디스코드에 계속 접속해 있을 필요 없이 REST API만 씁니다.

  1. 구독 테이블(SUBSCRIPTIONS_TABLE)을 읽어 키워드 → 사용자 목록을 만듭니다.
  2. 새 글의 제목·출처·구분(subtype)에 키워드가 들어 있으면 (대소문자 무시) 그 사용자에게 보낼 글로 모읍니다.
  3. 웹에서 "내 학교"를 정한 사용자(PROFILES_TABLE에 discordId가 있는 줄)는 학교 공지 중 내 학교 글만 받습니다.
     학교를 정하지 않은 사용자는 예전처럼 모든 학교 공지를 받습니다.
  4. 사용자마다 DM 한 통으로 묶어 보냅니다.

주의
  - 봇과 같은 서버에 있는 사용자에게만 DM을 보낼 수 있습니다. 못 보내면 로그만 남기고 넘어갑니다.
  - 게시일이 MAX_AGE_DAYS보다 오래된 글은 알리지 않습니다. 처음 배포했을 때나 새 사이트를 추가했을 때
    예전 글이 한꺼번에 "새 글"로 들어와도 알림이 쏟아지지 않게 하기 위해서입니다.

로컬 확인:
  python src/notify.py                 예시 데이터로 보낼 메시지만 출력 (디스코드에 보내지 않음)
  python src/notify.py --send <내 ID>  .env의 DISCORD_BOT_TOKEN으로 나에게 실제 DM 보내기
"""
import os
import time
from datetime import datetime, timedelta, timezone

API = "https://discord.com/api/v10"
KST = timezone(timedelta(hours=9))
MAX_AGE_DAYS = 3
MAX_ITEMS_PER_DM = 10
MAX_LENGTH = 2000  # 디스코드 메시지 글자 수 한도
CATEGORY_LABEL = {"univ": "대학 소식", "contest": "공모전·대회", "jobs": "취업·인턴", "tech": "테크 트렌드"}


# ── 구독 읽기 · 매칭 ───────────────────────────────────────────
def load_subscriptions(table):
    """{키워드: {사용자 ID, ...}}"""
    subs, kwargs = {}, {"ProjectionExpression": "userId, keyword"}
    while True:
        res = table.scan(**kwargs)
        for row in res["Items"]:
            subs.setdefault(row["keyword"], set()).add(str(row["userId"]))
        if "LastEvaluatedKey" not in res:
            return subs
        kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]


def load_schools(table):
    """{디스코드 사용자 ID: 내 학교} — 웹에서 학교를 정한 디스코드 사용자만. "other"(목록에 없는 학교)도 그대로 둡니다."""
    schools, kwargs = {}, {"ProjectionExpression": "discordId, school"}
    while True:
        res = table.scan(**kwargs)
        for row in res["Items"]:
            if row.get("discordId") and row.get("school"):
                schools[str(row["discordId"])] = row["school"]
        if "LastEvaluatedKey" not in res:
            return schools
        kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]


def only_my_school(targets, schools):
    """학교를 정한 사용자에게서 다른 학교 공지를 뺍니다. 남는 글이 없는 사용자는 목록에서 빠집니다."""
    result = {}
    for user, matches in targets.items():
        school = schools.get(user)
        if school:
            matches = [(it, kws) for it, kws in matches if it.get("category") != "univ" or it.get("subtype") == school]
        if matches:
            result[user] = matches
    return result


def is_recent(item, today=None):
    today = today or datetime.now(KST).date()
    try:
        posted = datetime.strptime(item["date"], "%Y-%m-%d").date()
    except (KeyError, ValueError):
        return False
    return (today - posted).days <= MAX_AGE_DAYS


def match(items, subs):
    """{사용자 ID: [(글, [맞은 키워드...]), ...]} — 글 순서는 들어온 순서 그대로."""
    lowered = [(kw, kw.lower(), users) for kw, users in subs.items()]
    result = {}
    for item in items:
        text = f"{item.get('title', '')} {item.get('source', '')} {item.get('subtype', '')}".lower()
        hits = {}  # 사용자 ID → 이 글에서 맞은 키워드
        for kw, kw_lower, users in lowered:
            if kw_lower in text:
                for user in users:
                    hits.setdefault(user, []).append(kw)
        for user, kws in hits.items():
            result.setdefault(user, []).append((item, sorted(kws)))
    return result


# ── 메시지 만들기 ──────────────────────────────────────────────
def _escape(text):
    """제목에 든 마크다운 기호가 서식으로 바뀌거나 링크가 깨지지 않게 막습니다."""
    for ch in "\\*_~`|[]>#":
        text = text.replace(ch, "\\" + ch)
    return text


def format_message(matches):
    """matches = [(글, [키워드...]), ...] → DM 본문 한 통."""
    text = f"🔔 구독 키워드에 맞는 새 글 {len(matches)}건"
    shown = 0
    for item, kws in matches[:MAX_ITEMS_PER_DM]:
        label = CATEGORY_LABEL.get(item.get("category"), "")
        deadline = f" · 마감 {item['deadline']}" if item.get("deadline") else ""
        block = (
            f"\n\n**[{_escape(item['title'])}](<{item['url']}>)**\n"  # <주소>: 미리보기 카드 끄기
            f"{label} · {_escape(item['source'])}{deadline} · 키워드 `{', '.join(kws)}`"
        )
        if len(text) + len(block) > MAX_LENGTH - 40:  # 끝에 붙일 "외 N건" 자리 남기기
            break
        text += block
        shown += 1
    if shown < len(matches):
        text += f"\n\n외 {len(matches) - shown}건은 웹에서 확인해 주세요."
    return text


# ── 디스코드 REST API ──────────────────────────────────────────
class DiscordError(Exception):
    pass


def _request(session, method, path, token, payload, retries=3):
    for _ in range(retries):
        res = session.request(
            method, f"{API}{path}", json=payload, timeout=10,
            headers={"Authorization": f"Bot {token}", "User-Agent": "csradar-bot (https://github.com, 1.0)"},
        )
        if res.status_code == 429:  # 요청 한도 초과: 디스코드가 알려준 시간만큼 기다렸다 다시
            wait = float(res.json().get("retry_after", 1))
            time.sleep(min(wait, 10))
            continue
        if res.status_code >= 400:
            raise DiscordError(f"HTTP {res.status_code} {res.text[:200]}")
        return res.json()
    raise DiscordError("요청 한도 초과로 재시도 실패")


def send_dm(session, token, user_id, content):
    channel = _request(session, "POST", "/users/@me/channels", token, {"recipient_id": user_id})
    _request(session, "POST", f"/channels/{channel['id']}/messages", token, {
        "content": content,
        "allowed_mentions": {"parse": []},  # 제목에 @everyone 같은 게 있어도 멘션되지 않게
    })


# ── 진입점 ─────────────────────────────────────────────────────
def notify(new_items, table=None, token=None, session=None, profiles_table=None):
    """새로 저장된 글로 DM을 보내고 {"users", "sent", "failed"} 개수를 돌려줍니다."""
    stats = {"users": 0, "sent": 0, "failed": 0}
    token = token if token is not None else os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        print("알림 건너뜀: DISCORD_BOT_TOKEN이 없음")
        return stats

    recent = [it for it in new_items if is_recent(it)]
    if not recent:
        return stats

    if table is None:
        import boto3
        table = boto3.resource("dynamodb").Table(os.environ["SUBSCRIPTIONS_TABLE"])
    targets = match(recent, load_subscriptions(table))
    if targets and any(it.get("category") == "univ" for it in recent):
        try:
            if profiles_table is None and os.environ.get("PROFILES_TABLE"):
                import boto3
                profiles_table = boto3.resource("dynamodb").Table(os.environ["PROFILES_TABLE"])
            if profiles_table is not None:
                targets = only_my_school(targets, load_schools(profiles_table))
        except Exception as e:  # 학교 설정을 못 읽으면 예전처럼 모두에게 보냄
            print(f"내 학교 설정 읽기 실패: {e}")
    stats["users"] = len(targets)
    if not targets:
        return stats

    if session is None:
        import requests
        session = requests.Session()
    for user_id, matches in targets.items():
        try:
            send_dm(session, token, user_id, format_message(matches))
            stats["sent"] += 1
        except Exception as e:  # 한 사람 실패(DM 차단, 서버에 없음 등)해도 나머지는 계속
            stats["failed"] += 1
            print(f"DM 실패 (사용자 {user_id}): {e}")
    print(f"알림: 대상 {stats['users']}명 → 보냄 {stats['sent']}, 실패 {stats['failed']}")
    return stats


if __name__ == "__main__":
    import sys

    today = datetime.now(KST).strftime("%Y-%m-%d")
    sample_items = [
        {"id": "t1", "category": "contest", "subtype": "해커톤", "source": "예시 주최", "title": "겨울 해커톤 참가자 모집",
         "fields": [], "date": today, "deadline": today, "url": "https://example.com/1"},
        {"id": "t2", "category": "contest", "subtype": "CTF", "source": "정보보호 동아리", "title": "화이트햇 CTF 예선 접수",
         "fields": ["security"], "date": today, "url": "https://example.com/2"},
    ]

    if len(sys.argv) == 3 and sys.argv[1] == "--send":
        from dotenv import load_dotenv
        load_dotenv()

        class FakeTable:  # 구독 테이블 대신: 나 혼자 "해커톤", "ctf"를 구독한 것으로
            def scan(self, **_):
                return {"Items": [{"userId": sys.argv[2], "keyword": "해커톤"}, {"userId": sys.argv[2], "keyword": "ctf"}]}

        notify(sample_items, table=FakeTable())
    else:
        subs = {"해커톤": {"111"}, "ctf": {"111", "222"}}
        for user, matches in match(sample_items, subs).items():
            print(f"── 사용자 {user}\n{format_message(matches)}\n")
