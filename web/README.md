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
css/style.css   스타일 (라이트/다크 자동)
js/data.js      카테고리·분야 정의 + 예시 데이터
js/api.js       데이터 접근 (API_BASE 비어 있으면 예시 데이터 사용)
js/app.js       라우팅(#all #univ #contest #jobs #tech #saved), 필터, 렌더링
```

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
