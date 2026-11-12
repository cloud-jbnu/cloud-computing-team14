# web — 컴공레이더 프론트엔드

컴퓨터 전공 학생을 위한 정보 모아보기 웹.

- 카테고리: 대학 소식 / 공모전·대회 / 취업·인턴 / 테크 트렌드(GitHub·최신기술·이슈)
- 분야 필터: 백엔드, 프론트엔드, AI, 데이터, 클라우드, 네트워크, 보안, 모바일 (여러 개 선택 가능)
- 검색, 최신순·마감임박순 정렬, 북마크(브라우저 저장), 마감 임박·GitHub 트렌딩 사이드 패널

## 실행

```bash
python -m http.server 8765 --directory web
```
→ http://localhost:8765

## 구조

```
index.html      화면 뼈대
css/style.css   스타일 (기본 밝은 화면, 헤더 버튼으로 어두운 화면 전환)
js/data.js      카테고리·분야 정의 + 예시 데이터
js/api.js       데이터 접근 (API_BASE 비어 있으면 예시 데이터 사용) + 주소 설정
js/auth.js      로그인 (Cognito + 디스코드, PKCE)
js/app.js       라우팅(#all #univ #contest #jobs #tech #saved), 필터, 렌더링
```

## 로그인 · 키워드 알림

디스코드로 로그인하면 오른쪽 "키워드 알림"에서 구독 키워드를 추가·삭제할 수 있습니다. 북마크는 로그인과 상관없이 브라우저에 저장됩니다.

`js/api.js` 맨 위의 `API_BASE`, `AUTH_BASE`, `AUTH_CLIENT_ID` 세 값을 모두 넣어야 켜집니다. 값은 배포 후 Outputs에 나옵니다 ([infra/README.md](../infra/README.md)). 비어 있으면 로그인 버튼을 눌렀을 때 안내 문구만 나옵니다.

로그인 후 돌아오는 주소는 `http://localhost:8765/`로 등록돼 있으므로, 로컬에서는 꼭 이 포트로 열어야 합니다.

## 백엔드 연결

`js/api.js`의 `API_BASE`에 API 주소를 넣으면 `GET {API_BASE}/items`에서 `{ "items": [...] }`를 받아옵니다.

```json
{
  "id": "c2",
  "category": "contest",          // univ | contest | jobs | tech
  "subtype": "CTF",               // 학교명, 대회 종류, 채용 형태, GitHub/최신기술/이슈
  "source": "정보보호 동아리 연합",
  "title": "화이트햇 CTF 2026 예선 참가 접수",
  "fields": ["security", "network"],
  "date": "2026-11-09",
  "deadline": "2026-11-18",       // 선택
  "url": "https://...",
  "repo": { "lang": "Go", "starsToday": 412 }   // GitHub 항목만
}
```

AI 요약은 아직 넣지 않았습니다. 나중에 Item에 `summary` 필드를 추가하고 `app.js`의 `itemHTML`에서 표시하면 됩니다.
