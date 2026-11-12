# API · 데이터 형식

crawler, web, bot이 모두 이 형식을 기준으로 맞춥니다. 바꿀 때는 PR에서 세 영역 담당자에게 알려 주세요.

## Item

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `id` | string | ✓ | 출처별로 고유한 값 (예: `kaist-cs-20261110-012`) |
| `category` | string | ✓ | `univ` · `contest` · `jobs` · `tech` |
| `subtype` | string | ✓ | 학교명 / 대회 종류(해커톤·공모전·경진대회·CTF) / 채용 형태(인턴·신입·채용연계) / `GitHub`·`최신기술`·`이슈` |
| `source` | string | ✓ | 출처 이름 (학과, 주최, 회사 등) |
| `title` | string | ✓ | 제목 |
| `fields` | string[] | ✓ | `backend` `frontend` `ai` `data` `cloud` `network` `security` `mobile` 중 0개 이상 |
| `date` | string | ✓ | 게시일 `YYYY-MM-DD` |
| `deadline` | string | | 마감일 `YYYY-MM-DD` |
| `url` | string | ✓ | 원문 주소 |
| `repo` | object | | GitHub 항목만. `{ "lang": "Go", "starsToday": 412 }` |
| `summary` | string[] | | (나중에) AI 요약 |

## GET /items

웹이 호출하는 목록 API.

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

웹은 Cognito를 거쳐 디스코드로 로그인합니다. 로그인하면 받는 액세스 토큰을 `Authorization: Bearer <토큰>` 헤더로 보내야 하는 API가 아래 `/me/...` 입니다. 토큰이 없거나 틀리면 `401`.

## Subscription (구독)

DynamoDB `SUBSCRIPTIONS_TABLE`에 한 줄이 "사용자 한 명 + 키워드 한 개"입니다. 웹과 봇이 같은 테이블을 씁니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `userId` | string | 디스코드 사용자 ID를 **문자열로**. 봇에서는 `str(interaction.user.id)` |
| `keyword` | string | 1~30자. 앞뒤 공백 없이, 사이 공백은 한 칸 |

한 사용자당 최대 20개.

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
