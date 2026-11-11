# bot

디스코드 봇. 사용자가 카테고리·분야·키워드를 구독하면 새 글이 올라올 때 DM으로 알려줍니다.

## 명령어 (계획)

| 명령어 | 동작 |
|---|---|
| `/구독 <키워드>` | 키워드 구독 (예: `/구독 보안`, `/구독 해커톤`) |
| `/해지 <키워드>` | 구독 해지 |
| `/목록` | 내 구독 목록 보기 |

## 구조

```
bot/
├─ src/
│  └─ bot.py
└─ requirements.txt
```

## 로컬 실행

`.env`에 `DISCORD_BOT_TOKEN`을 넣은 뒤:

```bash
pip install -r requirements.txt
python src/bot.py
```
