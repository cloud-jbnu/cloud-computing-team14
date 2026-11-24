"""봇 테스트 공통 설정. 네트워크·AWS 없이 돌아야 합니다.

실행: bot 폴더에서 `pytest`
"""
import sys
from pathlib import Path

import pytest

# Lambda에서는 src/가 최상위이므로 테스트에서도 `import interactions`로 불러옵니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class FakeTable:
    """구독 테이블 흉내: subscriptions.py가 쓰는 query·put_item·delete_item만."""
    def __init__(self, rows=()):
        self.rows = {(r["userId"], r["keyword"]) for r in rows}
        self.fail = False

    def _check(self):
        if self.fail:
            raise RuntimeError("DynamoDB 오류")

    def query(self, KeyConditionExpression):
        self._check()
        user_id = KeyConditionExpression.get_expression()["values"][1]
        return {"Items": [{"userId": u, "keyword": k} for u, k in self.rows if u == user_id]}

    def put_item(self, Item):
        self._check()
        self.rows.add((Item["userId"], Item["keyword"]))

    def delete_item(self, Key, ReturnValues=None):
        self._check()
        key = (Key["userId"], Key["keyword"])
        if key in self.rows:
            self.rows.discard(key)
            return {"Attributes": dict(Key)}
        return {}


@pytest.fixture
def table():
    return FakeTable()
