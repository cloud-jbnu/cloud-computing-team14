# 컴공레이더

컴퓨터 전공 학생을 위한 정보 모아보기 서비스.
주요 대학 소식, 공모전·대회, 취업·인턴, 테크 트렌드(GitHub·최신기술·이슈)를 한곳에 모으고
백엔드 / 프론트엔드 / AI / 데이터 / 클라우드 / 네트워크 / 보안 / 모바일 분야별로 걸러 볼 수 있게 합니다.
새 글은 디스코드로도 알림을 받을 수 있게 할 예정입니다.

클라우드 컴퓨팅 14조 · 권현무 · 서준원 · 안대희

## 구조

| 폴더 | 내용 | 담당 |
|---|---|---|
| [`web/`](web/) | 프론트엔드 (HTML/CSS/JS) | |
| [`crawler/`](crawler/) | 공지·공모전·채용·트렌드 크롤러 (Python, AWS Lambda) | |
| [`bot/`](bot/) | 디스코드 봇 (구독 명령어, DM 발송) | |
| [`infra/`](infra/) | AWS 설정 (Lambda, EventBridge, DynamoDB, S3, API Gateway) | |
| [`docs/`](docs/) | API 명세, 데이터 형식, 회의록 | |

담당 칸은 팀에서 정해서 채워 주세요.

## 데이터 흐름

```
EventBridge (주기 실행)
   └─▶ crawler (Lambda) ──▶ DynamoDB / S3
                               │
              API Gateway ◀────┤
                 └─▶ web       └─▶ bot (Discord DM)
```

## 시작하기

```bash
git clone <저장소 주소>
cd <저장소 폴더>
cp .env.example .env   # 각자 키를 채워 넣기 (절대 커밋하지 않기)
```

웹 실행:

```bash
python -m http.server 8765 --directory web
```

→ http://localhost:8765

## 협업 규칙

[CONTRIBUTING.md](CONTRIBUTING.md)를 먼저 읽어 주세요. 요약하면:

1. `main`에 직접 push하지 않습니다.
2. 이슈를 만들고 → 브랜치에서 작업하고 → PR을 올리고 → 1명이 확인하면 merge합니다.
3. API 키·토큰은 `.env`에만 넣고 커밋하지 않습니다.

## 일정 (4주)

| 주차 | 목표 |
|---|---|
| 1주차 | 요구사항 정리, AWS 환경 구성, 대상 사이트 분석 |
| 2주차 | 크롤러 개발, DB 설계, 웹 화면 |
| 3주차 | 디스코드 봇, 전체 파이프라인 통합 |
| 4주차 | 통합 테스트, 오류 수정, 최종 발표 준비 |

GitHub의 Milestones에 1~4주차를 만들어 이슈를 배정하면 진행률을 볼 수 있습니다.
