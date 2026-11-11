# infra

AWS 리소스 설정을 여기에 둡니다. 도구(AWS SAM, Terraform, 콘솔 수동 설정 기록 등)는 팀에서 정해 주세요.

## 필요한 리소스

| 리소스 | 용도 |
|---|---|
| Lambda `csradar-crawler` | `crawler/src/handler.py` 실행 |
| EventBridge 스케줄 | 크롤러 주기 실행 (예: `rate(30 minutes)`) |
| DynamoDB `csradar-items` | 수집한 글 (PK: `id`) |
| DynamoDB `csradar-subscriptions` | 디스코드 사용자별 구독 키워드 |
| S3 버킷 | 원문 HTML 백업 |
| API Gateway + Lambda | 웹에서 쓰는 `GET /items` |

## 주의

- 콘솔에서 직접 만든 설정은 이 폴더에 기록을 남겨 다른 팀원이 다시 만들 수 있게 합니다.
- 프리 티어 한도와 리전(`ap-northeast-2`)을 팀이 같이 씁니다.
- 액세스 키는 커밋하지 않습니다. 팀원마다 IAM 사용자를 따로 만들어 쓰는 걸 권장합니다.
