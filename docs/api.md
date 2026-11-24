# API · 데이터 형식

crawler, web, bot이 모두 이 형식을 기준으로 맞춥니다. 바꿀 때는 PR에서 세 영역 담당자에게 알려 주세요.

## Item

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `id` | string | ✓ | 출처별로 고유한 값 (예: `kaist-cs-20261110-012`) |
| `category` | string | ✓ | `univ` · `contest` · `jobs` · `tech` |
| `subtype` | string | ✓ | 학교명(전북대·충북대·경북대·부산대) / 대회 종류(해커톤·공모전·경진대회·CTF) / 채용 형태(인턴·신입·채용연계) / `GitHub`·`최신기술`·`이슈` |
| `source` | string | ✓ | 출처 이름 (학과, 주최, 회사 등) |
| `title` | string | ✓ | 제목 |
| `fields` | string[] | ✓ | `backend` `frontend` `ai` `data` `cloud` `network` `security` `mobile` 중 0개 이상 |
| `date` | string | ✓ | 게시일 `YYYY-MM-DD` |
| `deadline` | string | | 마감일 `YYYY-MM-DD` |
| `url` | string | ✓ | 원문 주소 |
| `repo` | object | | GitHub 항목만. `{ "lang": "Go", "starsToday": 412 }` |
| `summary` | string[] | | AI 요약 1~3줄 (한 줄 120자 이내). 크롤러가 새 글을 저장할 때 한 번 만들어 붙입니다. 요약에 실패했거나 요약 기능이 꺼져 있으면 이 필드가 없으니, 없을 때도 화면이 깨지지 않게 해 주세요 |

`id`는 `<사이트>-<글 번호>` 모양입니다 (`jbnu-219859`, `jumpit-55592439`, `github-owner.repo`). 앞부분(`jbnu`)은 크롤러가 중복 제거에 쓰므로 수집기를 만들 때 사이트마다 다른 값을 써야 합니다.

## GET /items

웹이 호출하는 목록 API.

- `?category=univ|contest|jobs|tech`를 주면 그 카테고리의 최신 200건을 돌려줍니다.
- 주지 않으면 카테고리마다 최신 200건씩(최대 800건)을 합쳐 최신순으로 돌려줍니다. 전체에서 200건만 자르면 글이 많은 테크 트렌드에 밀려 마감이 남은 채용·대회 글이 며칠 만에 빠지기 때문입니다.

```json
{
  "items": [
    {
      "id": "c2",
      "category": "contest",
      "subtype": "CTF",
      "source": "정보보호 동아리 연합",
      "title": "화이트햇 CTF 2026 예선 참가 접수",
      "fields": ["security", "network"],
      "date": "2026-11-09",
      "deadline": "2026-11-18",
      "url": "https://..."
    }
  ]
}
```

웹은 `web/js/api.js`의 `API_BASE`에 이 API 주소를 넣으면 예시 데이터 대신 실제 데이터를 씁니다.

## 로그인

웹은 Cognito로 로그인합니다. 방법은 두 가지입니다.

- **디스코드**: Cognito를 거쳐 디스코드로 로그인 (Cognito 사용자 이름 `Discord_<디스코드 ID>`)
- **이메일**: 웹 화면에서 이메일·비밀번호로 가입하고, 메일로 온 인증 코드를 넣은 뒤 로그인 (Cognito 사용자 이름 = 이메일 주소 소문자)

로그인하면 받는 액세스 토큰을 `Authorization: Bearer <토큰>` 헤더로 보내야 하는 API가 아래 `/me/...` 입니다. 토큰이 없거나 틀리면 `401`.

## Subscription (구독)

DynamoDB `SUBSCRIPTIONS_TABLE`에 한 줄이 "사용자 한 명 + 키워드 한 개"입니다. 웹과 봇이 같은 테이블을 씁니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `userId` | string | 디스코드 사용자 ID를 **문자열로** |
| `keyword` | string | 1~30자. 앞뒤 공백 없이, 사이 공백은 한 칸 |

한 사용자당 최대 20개. 이 규칙은 웹(`api/src/me.py`)과 봇(`bot/src/subscriptions.py`)에 따로 적혀 있으니 바꿀 때는 둘 다 고칩니다 (다르면 `tests/integration`이 실패).

## /me/subscriptions (로그인 필요)

| 요청 | 설명 |
|---|---|
| `GET /me/subscriptions` | 내 구독 목록 |
| `PUT /me/subscriptions` 본문 `{ "keyword": "해커톤" }` | 추가 (이미 있으면 그대로) |
| `DELETE /me/subscriptions?keyword=해커톤` | 삭제 |

셋 다 바뀐 뒤의 전체 목록을 돌려줍니다.

```json
{ "userId": "123456789012345678", "keywords": ["CTF", "해커톤"] }
```

잘못된 요청은 `400`과 `{ "message": "..." }`.

## POST /discord/interactions (디스코드 전용)

디스코드가 봇 명령어(`/구독 <키워드>`, `/해지 <키워드>`, `/목록`)를 전달하는 주소입니다 (`bot/src/interactions.py`). 웹은 부르지 않습니다.

- 로그인 토큰 대신 요청 헤더의 서명(`X-Signature-Ed25519`, `X-Signature-Timestamp`)을 앱의 Public Key로 검사합니다. 틀리면 `401`.
- 명령어를 쓴 사람의 디스코드 ID로 위 Subscription 테이블을 읽고 씁니다. `/me/subscriptions`와 같은 목록입니다.
- 답은 디스코드 형식(`{"type": 4, "data": {"content": "...", "flags": 64}}`)이고 쓴 사람에게만 보입니다.

## /me/profile (로그인 필요)

"내 학교" 설정입니다 (`api/src/user_profile.py`). 이메일·디스코드 로그인 모두 쓸 수 있습니다.

| 요청 | 설명 |
|---|---|
| `GET /me/profile` | 내 설정 |
| `PUT /me/profile` 본문 `{ "school": "전북대", "requestedSchool": null }` | 저장. `school`이 `null`이면 설정을 지움 |

둘 다 `{ "school": "전북대" | "other" | null, "requestedSchool": "서울대" | null }`를 돌려줍니다.

- `school`: `api/src/schools.py`의 학교 중 하나, 목록에 없으면 `"other"`, 정하지 않았으면 `null`. 그 밖의 값은 `400`.
- `requestedSchool`: `school`이 `"other"`일 때만 저장하는 학교 이름 (30자까지). 어느 학교 요청이 많은지 보려고 받습니다.
- 디스코드 사용자는 디스코드 ID도 같이 저장해, 크롤러가 학교 공지 DM을 내 학교 글로만 보낼 때 씁니다.

웹은 로그인하지 않아도 이 설정을 브라우저에 저장해 쓰고, 로그인하면 서버 값과 맞춥니다 (서버 값이 있으면 서버 값, 없으면 브라우저 값을 올림).

## POST /chat (로그인 필요)

수집한 글에서 골라 답하는 챗봇입니다 (`api/src/chat.py`, Gemini). 이메일·디스코드 로그인 모두 쓸 수 있습니다.

요청

```json
{ "message": "이번 주 마감인 AI 해커톤 있어?", "history": [{ "role": "user", "text": "..." }, { "role": "model", "text": "..." }] }
```

- `message`: 1~500자
- `history`: 앞선 대화 (선택). 최근 6개까지만 쓰고, 각 1000자로 자릅니다. `role`은 `user` 또는 `model`
- `school`: 내 학교 (선택). 학교를 말하지 않은 학교 공지 질문에서 이 학교 글을 고릅니다. 목록에 없는 값은 무시합니다.

응답 `200`

```json
{
  "answer": "이번 주에 마감하는 해커톤이 2개 있어요. ...",
  "items": [Item, ...],
  "web": null,
  "notice": null,
  "remaining": 27
}
```

- `answer`, `items`: 모아 둔 글에서 찾은 답과 글 (최대 5개, Item 형식 그대로). 마감이 지난 글은 고르지 않습니다.
- `web`: 모아 둔 글로는 답할 수 없는 질문(예: "하버드대 해커톤 알려줘")이면 Gemini의 Google 검색으로 찾은 답. 검색하지 않았으면 `null`.
  ```json
  { "answer": "...", "sources": [{ "title": "harvard.edu", "url": "https://..." }], "suggestionsHtml": "<style>...</style><div>...</div>" }
  ```
  `suggestionsHtml`은 Google이 준 "검색 추천" HTML입니다. Gemini API 약관상 웹 검색 답은 이 검색 추천과 함께 보여야 하고, 다른 내용과 섞으면 안 됩니다. 웹은 샌드박스 iframe에 넣어 보여 줍니다.
- `notice`: 웹 검색을 하려다 못 했을 때 그 이유 (사용자·사이트 전체 하루 한도를 다 씀, 검색 실패 등). 없으면 `null`.
- `remaining`: 오늘 남은 질문 수 (사용자당 하루 30번, 한국 시간 기준)

웹 검색은 돈이 드는 기능이라 따로 제한합니다. 사용자당 하루 `ChatSearchPerUser`번(기본 5), 사이트 전체 하루 `ChatSearchPerDay`번(기본 100). 질문 30번 안에서 세고, 한도를 넘으면 오류 없이 모아 둔 글로만 답합니다.

오류: `400` 질문이 비었거나 너무 김 · `401` 로그인 필요 · `429` 오늘 질문 수를 다 씀 · `502` Gemini 응답 실패 · `503` Gemini 키가 없음. 모두 `{ "message": "..." }`.

## /me/subscriptions 권한

키워드 알림은 디스코드 DM으로 보내므로 **디스코드로 로그인한 사용자만** 쓸 수 있습니다. 이메일로 로그인한 토큰으로 부르면 `403`.
(디스코드 사용자인지는 사용자 이름과 함께, Cognito가 자동으로 넣어 주는 `<User Pool ID>_Discord` 그룹으로 확인합니다.)
