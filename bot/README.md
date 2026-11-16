# bot

디스코드 봇. 사용자가 카테고리·분야·키워드를 구독하면 새 글이 올라올 때 DM으로 알려줍니다.

> **새 글 DM 알림은 이 폴더가 아니라 크롤러 Lambda([`crawler/src/notify.py`](../crawler/src/notify.py))가 보냅니다.**
> 같은 봇 토큰으로 REST API를 호출하므로 봇 프로그램을 켜 두지 않아도 알림이 갑니다.
> 알림을 받으려면 봇이 들어가 있는 디스코드 서버에 사용자도 들어가 있어야 합니다.
>
> 아래 `src/bot.py`는 명령어 연습용 뼈대이고 구독을 메모리에만 저장합니다. 웹·알림과 같은 구독 목록을 쓰려면
> Interactions Endpoint(Lambda)로 옮겨 DynamoDB `SUBSCRIPTIONS_TABLE`을 쓰게 해야 합니다 (다음 작업).

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
