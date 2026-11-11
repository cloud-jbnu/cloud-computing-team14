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

## 로컬 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/handler.py
```
