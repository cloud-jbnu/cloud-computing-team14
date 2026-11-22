"""테스트용 가짜 DynamoDB 테이블. dedupe·handler가 쓰는 기능만 흉내 냅니다."""


class ConditionalCheckFailedException(Exception):
    pass


class _Exceptions:
    ConditionalCheckFailedException = ConditionalCheckFailedException


class _Client:
    exceptions = _Exceptions

    def __init__(self, table):
        self.table = table
        self.batch_get_calls = []

    def batch_get_item(self, RequestItems):
        self.batch_get_calls.append(RequestItems)
        request = RequestItems[self.table.name]
        keys = request["Keys"]
        assert len(keys) <= 100, "BatchGetItem은 100건까지"
        assert len({tuple(k.items()) for k in keys}) == len(keys), "같은 키를 두 번 넣으면 안 됨"
        # unprocessed_first가 켜져 있으면 처음 요청에서 절반만 돌려주고 나머지는 UnprocessedKeys로
        now, later = keys, []
        if self.table.unprocessed_first and len(keys) > 1:
            self.table.unprocessed_first = False
            now, later = keys[: len(keys) // 2], keys[len(keys) // 2:]
        names = request["ExpressionAttributeNames"].values()
        rows = []
        for key in now:
            row = self.table.rows.get(key[self.table.key_name])
            if row is not None:
                rows.append({name: row[name] for name in names if name in row})
        res = {"Responses": {self.table.name: rows}}
        if later:
            res["UnprocessedKeys"] = {self.table.name: {**request, "Keys": later}}
        return res


class _Meta:
    def __init__(self, table):
        self.client = _Client(table)


class _BatchWriter:
    def __init__(self, table):
        self.table = table

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def put_item(self, Item):
        self.table.rows[Item[self.table.key_name]] = dict(Item)


class FakeTable:
    def __init__(self, name="table", key_name="id", rows=None):
        self.name = name
        self.key_name = key_name
        self.rows = {row[key_name]: dict(row) for row in (rows or [])}
        self.unprocessed_first = False
        self.meta = _Meta(self)

    def put_item(self, Item, ConditionExpression=None):
        key = Item[self.key_name]
        if ConditionExpression and key in self.rows:
            raise ConditionalCheckFailedException()
        self.rows[key] = dict(Item)

    def batch_writer(self, overwrite_by_pkeys=None):
        return _BatchWriter(self)
