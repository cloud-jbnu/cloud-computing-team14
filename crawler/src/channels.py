"""새 글을 디스코드 서버 채널에 올립니다.

crawler가 새로 저장한 글을 채널별로 나눠 요약과 함께 게시합니다. notify.py(구독자 DM)와 마찬가지로
봇이 접속해 있을 필요 없이 REST API만 씁니다.

채널
  - 학교 공지는 학교 이름과 같은 채널(전북대, 충북대, …), 나머지는 취업 · 공모전 · 트렌드 채널에 올립니다.
  - 채널 ID를 설정에 적지 않고, 서버(DISCORD_GUILD_ID)의 채널 목록에서 이름으로 찾습니다.
    이름이 맞는 채널이 없으면 그 글은 건너뛰고 로그에 남깁니다.

키워드 알림 (역할 멘션)
  - 서버에 이름이 "알림-"으로 시작하는 역할을 만들어 두면 뒷부분이 키워드가 됩니다. 예: "알림-해커톤"
  - 글의 제목·요약에 키워드가 들어 있으면 그 역할을 멘션합니다. 역할을 가진 사람에게만 알림이 갑니다.
  - 역할은 서버 관리자가 추가하면 다음 실행부터 바로 쓰입니다 (코드 수정 없음).

주의
  - 게시일이 3일(notify.MAX_AGE_DAYS)보다 오래된 글은 올리지 않습니다. 처음 배포했을 때 예전 글이 쏟아지지 않게 합니다.
  - DISCORD_BOT_TOKEN이나 DISCORD_GUILD_ID가 없으면 아무것도 하지 않습니다.

로컬 확인:
  python src/channels.py          예시 글로 만든 메시지를 출력 (디스코드에 보내지 않음)
  python src/channels.py --send   .env의 토큰·서버 ID로 예시 글을 실제 채널에 게시
"""
import os

import notify

ROLE_PREFIX = "알림-"
CATEGORY_CHANNEL = {"jobs": "취업", "contest": "공모전", "tech": "트렌드"}
CATEGORY_COLOR = {"univ": 0x3B82F6, "contest": 0xF59E0B, "jobs": 0x10B981, "tech": 0x8B5CF6}
TEXT_CHANNEL_TYPES = {0, 5}      # 일반 채널, 공지 채널

# 디스코드 한도: 메시지 하나에 임베드 10개, 임베드 글자 합계 6000자
MAX_EMBEDS = 10
MAX_EMBED_CHARS = 5500           # 6000자 한도에 여유를 둠
MAX_TITLE = 250
MAX_DESCRIPTION = 600
MAX_ROLE_MENTIONS = 10           # 메시지 하나에 멘션할 역할 수


# ── 서버 정보 읽기 ─────────────────────────────────────────────
def load_channels(session, token, guild_id):
    """{채널 이름: 채널 ID} — 글을 쓸 수 있는 종류의 채널만."""
    rows = notify._request(session, "GET", f"/guilds/{guild_id}/channels", token, None)
    return {row["name"]: row["id"] for row in rows if row.get("type") in TEXT_CHANNEL_TYPES}


def load_roles(session, token, guild_id):
    """[(키워드, 역할 ID)] — 이름이 "알림-"으로 시작하는 역할."""
    rows = notify._request(session, "GET", f"/guilds/{guild_id}/roles", token, None)
    roles = []
    for row in rows:
        name = row.get("name", "")
        keyword = name[len(ROLE_PREFIX):].strip() if name.startswith(ROLE_PREFIX) else ""
        if keyword:
            roles.append((keyword, row["id"]))
    return roles


# ── 글 → 채널 · 역할 ───────────────────────────────────────────
def channel_name(item):
    """이 글을 올릴 채널 이름. 학교 공지는 학교 이름(subtype)이 채널 이름입니다."""
    if item["category"] == "univ":
        return item["subtype"]
    return CATEGORY_CHANNEL.get(item["category"])


def matched_roles(item, roles):
    """제목·요약·출처에 키워드가 들어 있는 역할 ID 목록 (대소문자 무시)."""
    text = " ".join([item.get("title", ""), item.get("source", ""), item.get("subtype", ""), *item.get("summary", [])]).casefold()
    return [role_id for keyword, role_id in roles if keyword.casefold() in text]


# ── 메시지 만들기 ──────────────────────────────────────────────
def build_embed(item):
    """글 하나를 임베드(카드) 하나로: 제목 링크, 요약, 출처·마감일."""
    lines = [f"• {notify._escape(line)}" for line in item.get("summary", [])]
    footer = item["source"] + (f" · 마감 {item['deadline']}" if item.get("deadline") else "")
    if item.get("repo"):
        footer += f" · {item['repo']['lang'] or '언어 미상'} · ★ {item['repo']['starsToday']} today"
    embed = {
        "title": notify._escape(item["title"])[:MAX_TITLE],
        "url": item["url"],
        "color": CATEGORY_COLOR.get(item["category"], 0x6B7280),
        "footer": {"text": footer[:200]},
    }
    if lines:
        embed["description"] = "\n".join(lines)[:MAX_DESCRIPTION]
    return embed


def _size(embed):
    return len(embed["title"]) + len(embed.get("description", "")) + len(embed["footer"]["text"])


def build_messages(items, roles):
    """한 채널에 올릴 글들을 메시지 여러 개로 나눕니다 (임베드 10개, 글자 합계 한도)."""
    messages, embeds, mentions, size = [], [], [], 0

    def flush():
        if embeds:
            ids = mentions[:MAX_ROLE_MENTIONS]
            messages.append({
                "content": " ".join(f"<@&{role_id}>" for role_id in ids),
                "embeds": list(embeds),
                # 글 제목에 @everyone 같은 글자가 있어도 멘션되지 않게, 우리가 고른 역할만 허용
                "allowed_mentions": {"parse": [], "roles": ids},
            })

    for item in items:
        embed = build_embed(item)
        if embeds and (len(embeds) == MAX_EMBEDS or size + _size(embed) > MAX_EMBED_CHARS):
            flush()
            embeds, mentions, size = [], [], 0
        embeds.append(embed)
        size += _size(embed)
        for role_id in matched_roles(item, roles):
            if role_id not in mentions:
                mentions.append(role_id)
    flush()
    return messages


# ── 진입점 ─────────────────────────────────────────────────────
def post(new_items, token=None, guild_id=None, session=None):
    """새 글을 채널에 올리고 {"posted", "messages", "noChannel", "failed"} 개수를 돌려줍니다."""
    stats = {"posted": 0, "messages": 0, "noChannel": 0, "failed": 0}
    token = token if token is not None else os.environ.get("DISCORD_BOT_TOKEN", "")
    guild_id = guild_id if guild_id is not None else os.environ.get("DISCORD_GUILD_ID", "")
    if not token or not guild_id:
        print("채널 게시 건너뜀: DISCORD_BOT_TOKEN 또는 DISCORD_GUILD_ID가 없음")
        return stats

    recent = [it for it in new_items if notify.is_recent(it)]
    if not recent:
        return stats

    if session is None:
        import requests
        session = requests.Session()
    channels = load_channels(session, token, guild_id)
    try:
        roles = load_roles(session, token, guild_id)
    except Exception as e:  # 역할을 못 읽어도 멘션 없이 게시는 계속
        print(f"역할 목록 읽기 실패 (멘션 없이 게시): {e}")
        roles = []

    by_channel = {}
    for item in recent:
        by_channel.setdefault(channel_name(item), []).append(item)

    for name, items in by_channel.items():
        channel_id = channels.get(name)
        if not channel_id:
            stats["noChannel"] += len(items)
            print(f"채널 없음: '{name}' — {len(items)}건 건너뜀 (서버에 이 이름의 채널을 만들어 주세요)")
            continue
        for message in build_messages(items, roles):
            try:
                notify._request(session, "POST", f"/channels/{channel_id}/messages", token, message)
                stats["messages"] += 1
                stats["posted"] += len(message["embeds"])
            except Exception as e:  # 한 채널 실패(권한 없음 등)해도 나머지는 계속
                stats["failed"] += len(message["embeds"])
                print(f"채널 게시 실패 ('{name}'): {e}")
    print(f"채널 게시: {stats['posted']}건 (메시지 {stats['messages']}개), 채널 없음 {stats['noChannel']}, 실패 {stats['failed']}")
    return stats


if __name__ == "__main__":
    import json
    import sys
    from datetime import datetime

    today = datetime.now(notify.KST).strftime("%Y-%m-%d")
    samples = [
        {"id": "s1", "category": "univ", "subtype": "전북대", "source": "전북대 학사과", "title": "[예시] 동계 계절수업 수강신청 안내",
         "date": today, "url": "https://example.com/1", "summary": ["수강신청은 11월 18일 09시부터 19일 17시까지임", "최대 6학점까지 신청할 수 있음"]},
        {"id": "s2", "category": "contest", "subtype": "해커톤", "source": "예시 대학 연합", "title": "[예시] 겨울 오픈소스 해커톤 참가팀 모집",
         "date": today, "deadline": today, "url": "https://example.com/2", "summary": ["대학생 3~4인 팀으로 참가함", "12월 5일까지 온라인으로 접수함"]},
        {"id": "s3", "category": "tech", "subtype": "GitHub", "source": "GitHub Trending", "title": "example/repo",
         "date": today, "url": "https://github.com/example/repo", "repo": {"lang": "Go", "starsToday": 412}},
    ]

    if len(sys.argv) == 2 and sys.argv[1] == "--send":
        from dotenv import load_dotenv
        load_dotenv()
        print(post(samples))
    else:
        sample_roles = [("해커톤", "111"), ("수강신청", "222")]
        for sample in samples:
            print(f"── #{channel_name(sample)}")
            print(json.dumps(build_messages([sample], sample_roles), ensure_ascii=False, indent=1))
