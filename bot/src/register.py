"""디스코드에 명령어(/구독, /해지, /목록)를 등록합니다. 명령어 정의를 바꿨을 때만 한 번 실행하면 됩니다.

  python src/register.py            전체 등록 (모든 서버 + 봇과의 DM. 반영까지 최대 1시간)
  python src/register.py --guild    .env의 DISCORD_GUILD_ID 서버에만 등록 (바로 반영, 테스트용)
  python src/register.py --print    등록할 내용을 출력만

.env에 DISCORD_BOT_TOKEN, DISCORD_APPLICATION_ID가 필요합니다.
"""
import json
import os
import sys

API = "https://discord.com/api/v10"
STRING = 3  # 옵션 종류: 문자열

COMMANDS = [
    {
        "name": "구독", "description": "키워드를 구독합니다. 제목·출처에 키워드가 들어간 새 글을 DM으로 받아요",
        "options": [{"type": STRING, "name": "키워드", "description": "예: 해커톤, 장학금, 인턴 (1~30자)",
                     "required": True, "max_length": 30}],
    },
    {
        "name": "해지", "description": "키워드 구독을 해지합니다",
        "options": [{"type": STRING, "name": "키워드", "description": "해지할 키워드",
                     "required": True, "max_length": 30, "autocomplete": True}],
    },
    {"name": "목록", "description": "내 구독 목록을 봅니다"},
]


def register(token, application_id, guild_id=None, session=None):
    """명령어 전체를 COMMANDS로 바꿉니다 (여기 없는 예전 명령어는 지워짐). 등록된 명령어 목록을 돌려줍니다."""
    if session is None:
        import requests
        session = requests.Session()
    scope = f"/guilds/{guild_id}" if guild_id else ""
    res = session.put(
        f"{API}/applications/{application_id}{scope}/commands", json=COMMANDS, timeout=10,
        headers={"Authorization": f"Bot {token}", "User-Agent": "csradar-bot (https://github.com, 1.0)"},
    )
    if res.status_code >= 400:
        raise RuntimeError(f"등록 실패: HTTP {res.status_code} {res.text[:300]}")
    return res.json()


if __name__ == "__main__":
    if "--print" in sys.argv:
        print(json.dumps(COMMANDS, ensure_ascii=False, indent=1))
        sys.exit(0)

    from dotenv import load_dotenv
    load_dotenv()
    missing = [name for name in ("DISCORD_BOT_TOKEN", "DISCORD_APPLICATION_ID") if not os.environ.get(name)]
    guild = os.environ.get("DISCORD_GUILD_ID") if "--guild" in sys.argv else None
    if "--guild" in sys.argv and not guild:
        missing.append("DISCORD_GUILD_ID")
    if missing:
        sys.exit(f".env에 {', '.join(missing)} 값을 넣어 주세요.")
    done = register(os.environ["DISCORD_BOT_TOKEN"], os.environ["DISCORD_APPLICATION_ID"], guild)
    where = f"서버 {guild}" if guild else "전체"
    print(f"{where}에 등록: " + ", ".join("/" + c["name"] for c in done))
