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

## 새 글 알림 (디스코드 DM)

새로 저장된 글은 [`src/notify.py`](src/notify.py)가 키워드 구독자에게 DM으로 알립니다. 봇이 디스코드에 계속 접속해 있을 필요 없이 REST API만 씁니다.

- **매칭**: 글의 `title`·`source`·`subtype`에 구독 키워드가 들어 있으면 보냅니다 (대소문자 무시). 한 사람에게는 한 실행에 DM 한 통으로 묶어서, 최대 10건까지 보냅니다.
- **오래된 글은 알리지 않음**: 게시일이 3일(`MAX_AGE_DAYS`)보다 오래된 글은 저장만 하고 알리지 않습니다. 처음 배포했을 때나 새 사이트를 붙였을 때 예전 글로 알림이 쏟아지는 걸 막습니다.
- **봇과 같은 디스코드 서버에 있는 사용자에게만** 보낼 수 있습니다. DM을 막아 둔 사용자는 건너뛰고 로그에 `DM 실패`로 남깁니다.
- `DISCORD_BOT_TOKEN`이 비어 있으면 알림은 꺼지고 저장만 합니다.

```bash
python src/notify.py                       # 예시 데이터로 보낼 메시지만 출력
python src/notify.py --send <내 디스코드 ID>  # .env의 DISCORD_BOT_TOKEN으로 나에게 실제 DM
```

## 로컬 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/handler.py
```

로컬 실행은 DynamoDB에 저장하지 않고, 형식 검사를 거친 결과만 화면에 출력합니다. AWS 자격 증명이 없어도 됩니다.
