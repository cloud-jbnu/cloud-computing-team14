# infra

AWS 리소스는 전부 [`template.yaml`](template.yaml)(AWS SAM) 하나로 관리합니다.
**AWS Academy Learner Lab** 계정 기준이며, 배포는 클라우드 담당의 랩 계정 하나에서만 합니다.

## 만들어지는 것

| 리소스 | 이름(스택 `csradar` 기준) | 용도 |
|---|---|---|
| Lambda | `csradar-crawler` | `crawler/src/handler.py` 실행 |
| EventBridge 규칙 | (자동) | 크롤러 주기 실행, 기본 `rate(1 hour)` (30분~3시간만 허용) |
| Lambda + HTTP API | `csradar-items-api` | 웹이 쓰는 `GET /items` |
| DynamoDB | `csradar-ItemsTable-…` | 수집한 글. PK `id`, GSI `category-date-index` |
| DynamoDB | `csradar-SubscriptionsTable-…` | 구독. PK `userId` + SK `keyword`, GSI `keyword-index` |
| DynamoDB | `csradar-SeenTable-…` | 사이트 간 중복 비교용 키(60일 뒤 자동 삭제, TTL `expiresAt`)와 사이트별 밀린 글 목록(`source#사이트`, 만료 없음). PK `seenKey` |
| S3 | `csradar-rawbucket-…` | 원문 HTML 백업 (비공개) |
| Cognito User Pool | `csradar-users` | 로그인. 디스코드(OIDC) 로그인 + 이메일 회원가입 (인증 메일은 Cognito 기본 발신, 하루 50통) |
| Cognito 도메인 | `csradar-<계정ID>.auth.us-east-1.amazoncognito.com` | 로그인 주소 |
| Lambda + HTTP API | `csradar-me-api` | 로그인한 사용자의 키워드 구독 `/me/subscriptions` (JWT Authorizer로 토큰 검사) |
| Lambda + HTTP API | `csradar-profile-api` | "내 학교" 설정 `/me/profile` (로그인 필요) |
| DynamoDB | `csradar-ProfilesTable-…` | 사용자별 내 학교. PK `userId`(Cognito sub). 크롤러가 학교 공지 DM을 거를 때도 읽음 |
| Lambda + HTTP API | `csradar-chat-api` | 챗봇 `POST /chat` (로그인 필요). 모아 둔 글에서 골라 Gemini로 답하고, 없으면 Google 검색으로 찾음. `GeminiApiKey`가 없으면 503 |
| DynamoDB | `csradar-ChatUsageTable-…` | 챗봇 하루 질문 수(사용자당 30번)와 웹 검색 수(사용자별·사이트 전체). 이틀 뒤 자동 삭제, TTL `expiresAt`. PK `userDay` |

테이블·버킷 이름은 CloudFormation이 정하고, Lambda에는 환경변수 `ITEMS_TABLE`, `SUBSCRIPTIONS_TABLE`, `SEEN_TABLE`, `PROFILES_TABLE`, `RAW_BUCKET`(챗봇은 `CHAT_USAGE_TABLE`도)으로 들어갑니다.

## Learner Lab 제약과 대응

| 제약 | 대응 |
|---|---|
| IAM 역할을 새로 만들 수 없음 | 모든 Lambda에 기존 `LabRole` 지정 |
| 허용 리전이 제한됨 | `us-east-1` 사용 (`samconfig.toml`) |
| 자격 증명이 세션마다 바뀜 (약 4시간) | 랩을 켤 때마다 credentials 다시 붙여 넣기 |
| 계정이 학생 한 명 것 | 배포는 클라우드 담당만. 팀원은 PR로 코드 전달 |
| `ScheduleV2`(EventBridge Scheduler)는 역할이 필요 | 역할이 필요 없는 `Schedule`(EventBridge 규칙) 사용 |
| Cognito Identity Pool·SMS 인증은 역할이 필요 | 역할이 필요 없는 User Pool + JWT Authorizer만 사용 |

## 처음 한 번: 도구 설치

1. [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) 설치
2. [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) 설치
3. Python 3.12 (Lambda 런타임과 같은 버전)

## 랩을 켤 때마다: 자격 증명

1. Learner Lab → **Start Lab** → 동그라미가 초록색이 될 때까지 대기
2. **AWS Details → AWS CLI: Show** 내용을 `%USERPROFILE%\.aws\credentials`에 통째로 붙여 넣기
3. 확인:
   ```bash
   aws sts get-caller-identity
   ```

## 처음 한 번: 디스코드 앱 준비 (로그인용)

1. [디스코드 개발자 포털](https://discord.com/developers/applications)에서 앱을 엽니다 (봇과 같은 앱을 써도 됩니다).
2. **OAuth2** 메뉴에서 **Client ID**와 **Client Secret**을 확인합니다. Secret은 배포 명령에만 쓰고 파일이나 채팅에 남기지 않습니다.
3. 아래 배포가 끝난 뒤, Outputs의 `DiscordRedirectUri`를 **OAuth2 → Redirects**에 등록합니다.

## 배포

```bash
cd infra
sam build
sam deploy --parameter-overrides DiscordClientId=<Client ID> DiscordClientSecret=<Client Secret> DiscordBotToken=<Bot Token> DiscordGuildId=<서버 ID> GeminiApiKey=<Gemini 키>
```

- `DiscordClientId`, `DiscordClientSecret`은 기본값이 없어서 배포할 때마다 넘겨야 합니다.
- `DiscordBotToken`(개발자 포털 → **Bot → Token**)은 새 글 DM 알림과 서버 채널 게시에 씁니다. 빼면 둘 다 꺼지고 저장만 합니다.
- `DiscordGuildId`는 새 글을 올릴 디스코드 서버 ID입니다. 빼면 채널 게시만 꺼집니다. 채널·역할 준비는 [bot/README.md](../bot/README.md) 참고.
- `GeminiApiKey`([Google AI Studio](https://aistudio.google.com)에서 발급)는 새 글 AI 요약과 챗봇에 씁니다. 빼면 요약 없이 저장하고 챗봇은 꺼집니다. 모델을 바꾸려면 `GeminiModel=<모델 이름>`도 넘깁니다 (기본 `gemini-flash-lite-latest`).
- 챗봇 웹 검색(Google 검색) 한도: `ChatSearchPerUser`(사용자당 하루, 기본 5), `ChatSearchPerDay`(사이트 전체 하루, 기본 100). 둘 중 하나를 `0`으로 넘기면 웹 검색을 끕니다.
  - Gemini 3 이후 모델은 검색 한 번마다 요금이 붙고, 무료 요금제 키에서는 검색이 안 될 수 있습니다. 배포 전에 [Gemini 가격 페이지](https://ai.google.dev/gemini-api/docs/pricing)에서 "Grounding with Google Search" 한도를 확인하고 `ChatSearchPerDay`를 그보다 낮게 잡아 주세요.
  - 키의 요금제에서 기본 모델로 검색이 안 되면 `ChatSearchModel=<검색이 되는 모델>`로 검색에만 다른 모델을 쓸 수 있습니다. 검색이 실패해도 챗봇은 모아 둔 글로 답합니다.
- 토큰과 키는 다음 배포 때 다시 넘기지 않으면 SAM이 이전 값을 기억하지 못하고 빈 값이 되니 매번 같이 넘겨 주세요.
- 크롤러 주기는 `CrawlSchedule=rate(30 minutes)`처럼 바꿀 수 있지만 **30분~3시간**만 받습니다. 학교 게시판은 첫 쪽(10~20건)만 읽는데 바쁜 날은 하루 8건 넘게 올라와서, 주기가 길면 글을 놓칩니다. 더 길게 하려면 학교 수집기가 여러 쪽을 읽도록 먼저 고쳐야 합니다.
- 웹을 `http://localhost:8765`가 아닌 주소에서 열 거라면 `WebOrigin=https://내-주소`도 같이 넘깁니다 (끝에 `/` 없이). 로그인 후 돌아올 주소로 등록됩니다.
- 바뀌는 리소스 목록이 나오면 확인하고 `y`.
- 끝나면 **Outputs** 값을 `web/js/api.js` 맨 위에 넣습니다.

| Outputs | 넣을 곳 |
|---|---|
| `ApiUrl` | `API_BASE` |
| `AuthUrl` | `AUTH_BASE` |
| `AuthClientId` | `AUTH_CLIENT_ID` |
| `DiscordRedirectUri` | 디스코드 개발자 포털 → OAuth2 → Redirects |

## 확인

```bash
aws lambda invoke --function-name csradar-crawler out.json
```

```bash
curl "<ApiUrl>/items"
```

크롤러 로그는 CloudWatch → Log groups → `/aws/lambda/csradar-crawler`. 처음 배포한 뒤 첫 실행이면 이런 줄이 남습니다.

```
수집 163건 → 형식 오류 0, 실행 내 중복 2, 이미 있음 0, 사이트 간 중복 0, 새 글 161
[jbnu] 처음 수집하는 사이트: 지금 있는 글 12건은 저장만 하고 알리지 않음
[jumpit] 처음 수집하는 사이트: 지금 있는 글 58건은 저장만 하고 알리지 않음
… (사이트마다 한 줄)
새 글이 많아 30건만 처리하고 131건은 다음 실행으로 미룸
요약: 30건 중 30건 완료, 제목 되풀이라 뺀 글 0건 (요청 3번)
저장 30건
밀린 글 30건은 저장만 하고 게시·알림하지 않음
```

- 처음 배포하면 사이트 목록에 이미 있던 글이 한 번에 30건씩 들어오므로, 다 저장될 때까지 5~6번 실행됩니다 (기본 주기면 5~6시간).
- 이렇게 **밀린 글은 저장과 요약만 하고 채널 게시와 키워드 DM은 보내지 않습니다.** 게시일이 없는 사이트(점핏 등)는 몇 주 된 글도 수집한 날짜가 되어, 그대로 알리면 오래된 글이 한꺼번에 쏟아지기 때문입니다. 배포한 뒤 새로 올라온 글은 처음부터 평소처럼 알립니다.
- 나중에 새 사이트를 붙여도 그 사이트의 밀린 글은 같은 방식으로 조용히 저장됩니다.
- 바로 한 번 더 실행했을 때 같은 글이 다시 저장되거나 채널에 또 올라오지 않으면 중복 제거가 동작하는 것입니다.
- 채널 게시를 테스트하려고 밀린 글도 다시 알리고 싶다면, ItemsTable에서 해당 글과 SeenTable의 `source#사이트` 항목을 지우고 다시 실행합니다.

로그인 확인: 웹(`http://localhost:8765`)에서 **로그인** → **디스코드로 로그인** → 디스코드 승인 → 오른쪽 "키워드 알림"에 키워드를 추가해 봅니다.
이메일 가입은 **로그인** → **이메일로 회원가입** → 메일로 온 6자리 코드 입력 → 자동 로그인까지 되는지 봅니다. 이메일 사용자는 "키워드 알림"에 디스코드 안내만 보이면 맞습니다.
인증 메일이 안 오면 스팸함을 확인해 주세요 (발신: `no-reply@verificationemail.com`). Cognito 기본 발신은 하루 50통까지입니다.
토큰 없이 부르면 401이 나와야 합니다.

```bash
curl -i "<ApiUrl>/me/subscriptions"
```

챗봇 확인: 로그인한 뒤 오른쪽 아래 **AI에게 물어보기** → 추천 질문을 눌러 봅니다. 답과 함께 글 카드가 나오면 됩니다.
웹 검색은 "하버드대 해커톤 알려줘"처럼 모아 둔 글에 없는 걸 물어봅니다. "웹 검색 결과" 칸에 답, 출처, Google 검색 추천이 나오면 됩니다. "웹 검색에 실패해서…"가 나오면 CloudWatch 로그에서 `웹 검색 실패: HTTP …`를 확인해 주세요 (대개 키의 요금제·모델 문제).
"챗봇이 아직 연결되지 않았어요"가 나오면 배포할 때 `GeminiApiKey`를 넘기지 않은 것입니다. 답이 늦거나 실패하면 CloudWatch 로그 그룹 `/aws/lambda/csradar-chat-api`를 봅니다 (HTTP API는 30초가 지나면 끊습니다).

처음 로그인했을 때 `GET /me/subscriptions` 응답의 `userId`가 내 디스코드 사용자 ID(디스코드에서 프로필 우클릭 → ID 복사)와 같은지 확인해 주세요. 봇과 같은 구독 목록을 쓰려면 이 값이 같아야 합니다.

## 정리 (크레딧 아끼기)

DynamoDB(온디맨드), Lambda, HTTP API는 안 쓰면 거의 비용이 없습니다.
크롤러 주기를 짧게 바꿨다면 테스트가 끝난 뒤 다시 늘려 주세요. 전부 지우려면:

```bash
sam delete
```

## 아직 안 한 것

- 디스코드 봇 명령어(`/구독` 등)를 Interactions Endpoint(Lambda + HTTP API)로 옮겨 구독 테이블을 쓰게 하기 — 지금은 봇 메모리에만 있어서 웹에서 넣은 구독과 합쳐지지 않습니다. 구독 관리는 웹에서, 새 글 DM은 크롤러에서 이미 됩니다
- 디스코드 토큰은 SSM Parameter Store에 넣고 Lambda가 읽게 할 예정
