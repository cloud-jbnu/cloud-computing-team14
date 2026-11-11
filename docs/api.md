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
