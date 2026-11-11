"""Lambda 진입점. EventBridge가 주기적으로 호출합니다.

각 수집기(sources/*.py)의 fetch()를 돌려 Item 목록을 모은 뒤 저장합니다.
저장(DynamoDB/S3) 부분은 infra 담당과 테이블 설계가 정해지면 채웁니다.
"""
import json

from sources import example_univ

# 수집기 등록 — 새 사이트를 만들면 여기에 추가
SOURCES = [
    example_univ,
]


def collect():
    items = []
    for source in SOURCES:
        try:
            items.extend(source.fetch())
        except Exception as e:  # 한 사이트가 실패해도 나머지는 계속
            print(f"[{source.__name__}] 수집 실패: {e}")
    return items


def save(items):
    # TODO: DynamoDB에 이미 있는 id는 건너뛰고 새 글만 저장
    print(f"{len(items)}건 수집")


def lambda_handler(event, context):
    items = collect()
    save(items)
    return {"statusCode": 200, "body": json.dumps({"collected": len(items)})}


if __name__ == "__main__":
    for it in collect():
        print(it)
