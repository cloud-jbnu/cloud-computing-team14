# infra

AWS 리소스는 전부 [`template.yaml`](template.yaml)(AWS SAM) 하나로 관리합니다.
**AWS Academy Learner Lab** 계정 기준이며, 배포는 클라우드 담당의 랩 계정 하나에서만 합니다.

## 만들어지는 것

| 리소스 | 이름(스택 `csradar` 기준) | 용도 |
|---|---|---|
| Lambda | `csradar-crawler` | `crawler/src/handler.py` 실행 |
| EventBridge 규칙 | (자동) | 크롤러 주기 실행, 기본 `rate(1 hour)` |
| Lambda + HTTP API | `csradar-items-api` | 웹이 쓰는 `GET /items` |
| DynamoDB | `csradar-ItemsTable-…` | 수집한 글. PK `id`, GSI `category-date-index` |
| DynamoDB | `csradar-SubscriptionsTable-…` | 구독. PK `userId` + SK `keyword`, GSI `keyword-index` |
| S3 | `csradar-rawbucket-…` | 원문 HTML 백업 (비공개) |

테이블·버킷 이름은 CloudFormation이 정하고, Lambda에는 환경변수 `ITEMS_TABLE`, `SUBSCRIPTIONS_TABLE`, `RAW_BUCKET`으로 들어갑니다.

## Learner Lab 제약과 대응

| 제약 | 대응 |
|---|---|
| IAM 역할을 새로 만들 수 없음 | 모든 Lambda에 기존 `LabRole` 지정 |
| 허용 리전이 제한됨 | `us-east-1` 사용 (`samconfig.toml`) |
| 자격 증명이 세션마다 바뀜 (약 4시간) | 랩을 켤 때마다 credentials 다시 붙여 넣기 |
| 계정이 학생 한 명 것 | 배포는 클라우드 담당만. 팀원은 PR로 코드 전달 |
| `ScheduleV2`(EventBridge Scheduler)는 역할이 필요 | 역할이 필요 없는 `Schedule`(EventBridge 규칙) 사용 |

## 처음 한 번: 도구 설치

1. [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) 설치
2. [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) 설치
3. Python 3.12 (Lambda 런타임과 같은 버전)

## 랩을 켤 때마다: 자격 증명

1. Learner Lab → **Start Lab** → 동그라미가 초록색이 될 때까지 대기
2. **AWS Details → AWS CLI: Show** 내용을 `%USERPROFILE%\.aws\credentials`에 통째로 붙여 넣기
3. 확인:
   ```bash
   aws sts get-caller-identity
   ```

## 배포

```bash
cd infra
sam build
sam deploy
```

- 처음엔 `sam deploy --guided`로 해도 됩니다. 값은 `samconfig.toml`에 이미 들어 있어서 Enter만 누르면 됩니다.
- 바뀌는 리소스 목록이 나오면 확인하고 `y`.
- 끝나면 **Outputs**의 `ApiUrl`을 `web/js/api.js`의 `API_BASE`에 넣습니다.

## 확인

```bash
aws lambda invoke --function-name csradar-crawler out.json
```

```bash
curl "<ApiUrl>/items"
```

크롤러 로그는 CloudWatch → Log groups → `/aws/lambda/csradar-crawler`.

## 정리 (크레딧 아끼기)

DynamoDB(온디맨드), Lambda, HTTP API는 안 쓰면 거의 비용이 없습니다.
크롤러 주기를 짧게 바꿨다면 테스트가 끝난 뒤 다시 늘려 주세요. 전부 지우려면:

```bash
sam delete
```

## 아직 안 한 것

- 크롤러가 DynamoDB에 저장하는 부분 (`crawler/src/handler.py`의 `save()`)
- 디스코드 봇의 Interactions Endpoint (Lambda + HTTP API) — 봇 담당과 방식 확정 후 추가
- 디스코드 토큰은 SSM Parameter Store에 넣고 Lambda가 읽게 할 예정
