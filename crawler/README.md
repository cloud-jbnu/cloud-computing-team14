# crawler

대학 공지, 공모전·대회, 채용·인턴, GitHub 트렌딩 등을 수집해 공통 형식([docs/api.md](../docs/api.md)의 Item)으로 저장합니다.
AWS Lambda에서 EventBridge 스케줄로 실행됩니다.

## 구조

```
crawler/
├─ src/
│  ├─ handler.py        Lambda 진입점
│  └─ sources/          사이트별 수집기 (사이트 하나당 파일 하나)
└─ requirements.txt
```

## 새 사이트 추가하기

1. `src/sources/`에 파일을 만들고 `fetch()`가 Item 딕셔너리 목록을 돌려주게 합니다.
2. `handler.py`의 `SOURCES`에 등록합니다.

## 저장 방식

Lambda에서 실행되면 모은 Item을 DynamoDB(`ITEMS_TABLE`)에 저장합니다.

- **새 글만 저장**: 같은 `id`가 이미 있으면 건너뜁니다. 덮어쓰지 않으므로 `id`는 출처별로 고유하고 매번 같은 값이 나오게 만들어 주세요 (예: 게시글 번호 사용).
- **형식 검사**: [docs/api.md](../docs/api.md)의 필수 필드가 없거나, `category`가 네 가지 중 하나가 아니거나, `date`가 `YYYY-MM-DD`가 아니면 저장하지 않고 로그에 이유를 남깁니다. `fields`에서 정해진 값이 아닌 것은 빼고 저장합니다.
- 실행 결과는 CloudWatch 로그에 `수집 N건 → 새로 저장 …, 이미 있음 …, 형식 오류 …`로 남습니다.

## 로컬 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/handler.py
```

로컬 실행은 DynamoDB에 저장하지 않고, 형식 검사를 거친 결과만 화면에 출력합니다. AWS 자격 증명이 없어도 됩니다.
