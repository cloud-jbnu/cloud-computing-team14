# 협업 규칙

## 작업 순서

1. **이슈 만들기** — 할 일 하나에 이슈 하나. 담당자(Assignees)와 주차(Milestone)를 지정합니다.
2. **브랜치 만들기** — 최신 `main`에서 시작합니다.
   ```bash
   git switch main
   git pull
   git switch -c feat/web-bookmark
   ```
3. **커밋하고 올리기**
   ```bash
   git add .
   git commit -m "feat(web): 북마크 페이지 추가"
   git push -u origin feat/web-bookmark
   ```
4. **PR 올리기** — GitHub에서 Pull Request를 만들고 본문에 `Closes #이슈번호`를 적습니다.
5. **리뷰 후 merge** — 팀원 1명이 확인하면 **Squash and merge** 합니다. merge한 브랜치는 삭제합니다.

## 브랜치 이름

| 접두어 | 용도 | 예 |
|---|---|---|
| `feat/` | 새 기능 | `feat/crawler-kaist` |
| `fix/` | 버그 수정 | `fix/web-dday` |
| `docs/` | 문서 | `docs/api-spec` |
| `chore/` | 설정, 정리 | `chore/gitignore` |

## 커밋 메시지

`종류(영역): 무엇을 했는지` 형식으로 씁니다.

```
feat(crawler): KAIST 전산학부 공지 파싱
fix(web): 마감 지난 글 D-day 표시 오류
docs: API 응답 형식 추가
```

영역: `web`, `crawler`, `bot`, `infra`, `docs`

## 비밀 값 다루기

- AWS 키, 디스코드 봇 토큰, 각종 API 키는 **`.env` 파일에만** 넣습니다. `.env`는 `.gitignore`에 들어 있어 올라가지 않습니다.
- 새 환경변수가 생기면 값은 빼고 이름만 `.env.example`에 추가합니다.
- 실수로 키를 올렸다면 지우는 것만으로는 부족합니다. **바로 팀에 알리고 키를 재발급**하세요. Git 기록에 남기 때문입니다.
- GitHub Actions에서 쓸 키는 저장소 **Settings → Secrets and variables → Actions**에 넣습니다.

## 충돌이 났을 때

```bash
git switch main
git pull
git switch 내-브랜치
git merge main
```

충돌 난 파일을 고치고 `git add` → `git commit` → `git push` 하면 PR이 갱신됩니다.
모르겠으면 혼자 해결하지 말고 해당 파일 담당자와 같이 봅니다.
