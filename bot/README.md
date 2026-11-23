# bot

디스코드 봇. 사용자가 카테고리·분야·키워드를 구독하면 새 글이 올라올 때 DM으로 알려줍니다.

봇 프로그램을 켜 두는 서버는 없습니다. 하는 일이 둘로 나뉘어 각각 Lambda에서 돕니다.

| 하는 일 | 어디서 | 언제 |
|---|---|---|
| 명령어 `/구독` `/해지` `/목록` | 이 폴더의 [`src/interactions.py`](src/interactions.py) (Lambda `csradar-bot`) | 사용자가 명령어를 쓸 때 디스코드가 호출 |
| 새 글 DM 알림, 서버 채널 게시 | 크롤러 Lambda ([`notify.py`](../crawler/src/notify.py), [`channels.py`](../crawler/src/channels.py)) | 크롤러가 새 글을 저장한 직후 |

- 구독은 웹의 "키워드 알림"과 **같은 DynamoDB 테이블**(`SUBSCRIPTIONS_TABLE`)에 저장합니다. 디스코드에서 넣은 키워드가 웹에 보이고, 웹에서 넣은 키워드가 `/목록`에 보입니다.
- 키워드는 1~30자, 한 사람당 20개까지 (웹과 같은 규칙, [docs/api.md](../docs/api.md)).
- DM을 받으려면 봇이 들어가 있는 디스코드 서버에 사용자도 들어가 있어야 합니다.

## 명령어

| 명령어 | 동작 |
|---|---|
| `/구독 <키워드>` | 키워드 구독 (예: `/구독 해커톤`, `/구독 장학금`). 새 글의 제목·출처·구분에 키워드가 들어 있으면 DM |
| `/해지 <키워드>` | 구독 해지. 입력하는 동안 내 구독 목록이 선택지로 뜹니다 |
| `/목록` | 내 구독 목록 보기 |

답장은 명령어를 쓴 사람에게만 보입니다. 서버 채널에서도, 봇과의 DM에서도 쓸 수 있습니다.

### 명령어 켜기 (배포한 뒤 한 번)

1. [개발자 포털](https://discord.com/developers/applications) → 앱 → **General Information**의 **Public Key**를 복사해, 배포할 때 `DiscordPublicKey=<Public Key>`로 넘깁니다 ([infra/README.md](../infra/README.md)). 비밀 값은 아니지만 이 값이 없으면 Lambda가 모든 요청을 거부합니다.
2. 배포 Outputs의 `DiscordInteractionsUrl`을 같은 화면의 **Interactions Endpoint URL**에 넣고 저장합니다. 디스코드가 그 자리에서 확인 요청을 보내 보고, 통과해야 저장됩니다. "could not be verified"가 나오면 Public Key가 맞는지, 배포가 끝났는지 확인합니다.
3. 명령어를 등록합니다 (`.env`에 `DISCORD_BOT_TOKEN`, `DISCORD_APPLICATION_ID` 필요).
   ```bash
   cd bot
   pip install -r requirements.txt
   python src/register.py --guild   # .env의 DISCORD_GUILD_ID 서버에만, 바로 반영 (테스트용)
   python src/register.py           # 모든 서버 + 봇과의 DM, 반영까지 최대 1시간
   ```
   명령어 이름·옵션을 바꿨을 때만 다시 실행하면 됩니다. 코드만 고쳤다면 `sam deploy`로 충분합니다.
4. 디스코드에서 `/구독 해커톤` → `/목록`, 그리고 웹에 디스코드로 로그인해 "키워드 알림"에 같은 키워드가 보이는지 확인합니다.

봇을 서버에 초대할 때 scope에 `bot`과 함께 **`applications.commands`** 도 체크해야 서버에서 명령어가 보입니다.

## 서버 채널에 새 글 올리기 (크롤러가 게시)

크롤러 Lambda([`crawler/src/channels.py`](../crawler/src/channels.py))가 새 글을 요약과 함께 서버 채널에 올립니다. 이것도 봇 프로그램을 켜 둘 필요가 없습니다. 서버에서 한 번만 아래를 준비해 주세요.

### 1. 채널 만들기

채널 **이름이 정확히 같아야** 크롤러가 찾습니다. 이름이 없는 채널의 글은 건너뛰고 로그에 `채널 없음`으로 남습니다.

| 채널 이름 | 올라오는 글 |
|---|---|
| `전북대` `충북대` `경북대` `부산대` | 그 학교의 전체 공지 |
| `취업` | 채용 공고 (신입·인턴) |
| `공모전` | 대회·해커톤 |
| `트렌드` | GitHub 트렌딩, 개발 뉴스 |

학교 채널은 디스코드의 "카테고리"(예: `학교 공지`)로 묶어 두면 접어 둘 수 있습니다. 관심 없는 채널은 각자 알림을 끄면 됩니다.

### 2. 봇 권한

봇을 서버에 초대할 때(개발자 포털 → **OAuth2 → URL Generator**, scope `bot` + `applications.commands`) 아래 권한을 줍니다.

- 채널 보기, 메시지 보내기, 링크 첨부(Embed Links)
- `@everyone`, `@here`, 모든 역할 멘션하기 — 키워드 역할을 멘션하는 데 필요합니다. 이 권한을 주기 싫으면 역할마다 "누구나 이 역할을 멘션할 수 있음"을 켜도 됩니다.

### 3. 키워드 알림 역할

특정 키워드가 들어간 글만 알림을 받고 싶은 사람을 위한 기능입니다.

1. 서버 설정 → 역할에서 이름이 **`알림-`으로 시작하는** 역할을 만듭니다. 예: `알림-해커톤`, `알림-장학금`, `알림-인턴`, `알림-AI`
2. 새 글의 제목·요약에 `알림-` 뒤의 글자(`해커톤`)가 들어 있으면, 크롤러가 그 글을 올릴 때 역할을 멘션합니다. 그 역할을 가진 사람에게만 알림이 갑니다.
3. 역할은 언제든 추가·삭제할 수 있고, 다음 크롤러 실행부터 바로 반영됩니다.

멤버가 역할을 스스로 고르게 하려면 둘 중 하나를 씁니다 (코드 작업 없음).

- **디스코드 기본 기능**: 서버 설정 → 커뮤니티 활성화 → **채널 및 역할(온보딩)** 에서 질문("어떤 알림을 받을까요?")과 선택지별 역할을 연결합니다.
- **반응 역할 봇**: Carl-bot 같은 봇으로 "이모지를 누르면 역할 받기" 메시지를 만듭니다.

채널 전체 알림은 꺼 두고 `@멘션만` 받도록 해 두면, 고른 키워드의 글만 알림이 옵니다.

### 4. 서버 ID 넘기기

디스코드 설정 → 고급 → **개발자 모드**를 켠 뒤, 서버 이름 우클릭 → **서버 ID 복사**. 배포할 때 `DiscordGuildId`로 넘깁니다 ([infra/README.md](../infra/README.md)).

### 로컬에서 확인

```bash
cd crawler
python src/channels.py          # 예시 글로 만든 메시지를 출력만
python src/channels.py --send   # .env의 DISCORD_BOT_TOKEN, DISCORD_GUILD_ID로 예시 글 3건을 실제 채널에 게시
```

## 구조

```
bot/
├─ src/
│  ├─ interactions.py   Lambda 진입점: 서명 검사 → 명령어 처리
│  ├─ subscriptions.py  구독 저장(DynamoDB)과 답장 문구
│  ├─ register.py       디스코드에 명령어 등록
│  ├─ bot.py            Lambda 없이 내 컴퓨터에서 봇을 켜 두는 방식 (시험용)
│  └─ requirements.txt  Lambda에 같이 넣을 패키지 (PyNaCl)
├─ tests/               네트워크·AWS 없이 도는 테스트
└─ requirements.txt     로컬 개발용
```

요청이 디스코드에서 온 것인지는 [서명(Ed25519)](https://discord.com/developers/docs/interactions/overview#setting-up-an-endpoint-validating-security-request-headers)으로 확인합니다. 주소를 아는 누군가가 남의 사용자 ID로 구독을 바꾸는 요청을 보내도 서명이 없어 401로 거부됩니다.

## 테스트

```bash
cd bot
pip install -r requirements.txt
pytest
```

웹·크롤러와 이어서 보는 테스트는 [tests/integration/](../tests/integration/)에 있습니다.

## 내 컴퓨터에서 봇 켜기 (선택)

Lambda를 배포하지 않고 명령어를 시험할 때만 씁니다. `.env`에 `DISCORD_BOT_TOKEN`, `SUBSCRIPTIONS_TABLE`(배포 Outputs의 `SubscriptionsTableName`)과 AWS 자격 증명이 필요합니다.

```bash
python src/bot.py
```

개발자 포털에 Interactions Endpoint URL을 넣어 둔 상태에서는 명령어가 Lambda로만 가고 이 프로그램에는 오지 않습니다.
