"""통합 테스트 도구: AWS와 디스코드를 흉내 내, Lambda 4개를 배포한 것처럼 이어서 돌립니다.

  - DynamoDB  moto(메모리 안의 가짜 AWS)에 infra/template.yaml에 적힌 그대로 테이블을 만듭니다.
              템플릿의 키·인덱스와 코드가 안 맞으면 여기서 드러납니다.
  - 환경변수  템플릿의 Environment를 읽어 Lambda가 받는 것과 같은 이름으로 넣습니다.
  - 디스코드  FakeDiscord가 REST API를 흉내 내고, 받은 메시지를 기록하며 디스코드 한도를 검사합니다.
  - Gemini    FakeDiscord.post()가 요약 요청에 정해진 요약을 돌려줍니다.
  - 요청      web_event()는 API Gateway가 로그인 검사를 끝낸 뒤 넘겨 주는 모양,
              discord_event()는 디스코드가 서명해서 보내는 모양을 만듭니다.
"""
import json
import os
import re
import sys
from pathlib import Path

import yaml
from nacl.signing import SigningKey

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "infra" / "template.yaml"
SRC_DIRS = [ROOT / "crawler" / "src", ROOT / "api" / "src", ROOT / "bot" / "src"]
LAMBDA_MODULES = ("handler", "items", "me", "interactions")

BOT_TOKEN = "test-bot-token"
GUILD_ID = "900000000000000001"
SIGNING_KEY = SigningKey.generate()   # 디스코드가 요청에 서명하는 키 역할 (공개 키가 DiscordPublicKey)

# 배포할 때 --parameter-overrides로 넘기는 값
PARAMETERS = {
    "DiscordBotToken": BOT_TOKEN,
    "DiscordGuildId": GUILD_ID,
    "DiscordPublicKey": SIGNING_KEY.verify_key.encode().hex(),
    "GeminiApiKey": "test-gemini-key",
    "GeminiModel": "gemini-test",
}


# ── 템플릿 읽기 ────────────────────────────────────────────────
class _Loader(yaml.SafeLoader):
    pass


def _tag(loader, suffix, node):
    """!Ref X → {"Ref": "X"}, !Sub "..." → {"Sub": "..."} (CloudFormation 태그를 그대로 값으로)"""
    if isinstance(node, yaml.ScalarNode):
        return {suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {suffix: loader.construct_sequence(node, deep=True)}
    return {suffix: loader.construct_mapping(node, deep=True)}


_Loader.add_multi_constructor("!", _tag)


def load_template():
    return yaml.load(TEMPLATE.read_text(encoding="utf-8"), Loader=_Loader)


def create_tables(template, dynamodb):
    """템플릿의 DynamoDB 테이블을 모두 만듭니다. {템플릿의 이름: 실제 테이블 이름}"""
    names = {}
    for logical, resource in template["Resources"].items():
        if resource["Type"] != "AWS::DynamoDB::Table":
            continue
        props = resource["Properties"]
        args = {key: props[key] for key in ("AttributeDefinitions", "KeySchema", "BillingMode", "GlobalSecondaryIndexes") if key in props}
        names[logical] = f"csradar-{logical}-TEST"
        dynamodb.create_table(TableName=names[logical], **args)
    return names


def lambda_env(template, tables, parameters=None):
    """Lambda들이 받는 환경변수를 템플릿에서 읽어 값으로 풉니다 (!Ref 테이블 → 테이블 이름, !Ref 파라미터 → 넘긴 값)."""
    parameters = {**PARAMETERS, **(parameters or {})}
    defaults = {name: spec.get("Default", "") for name, spec in template["Parameters"].items()}
    sources = [template["Globals"]["Function"]["Environment"]["Variables"]]
    for resource in template["Resources"].values():
        if resource["Type"] == "AWS::Serverless::Function":
            sources.append(resource["Properties"].get("Environment", {}).get("Variables", {}))
    env = {}
    for variables in sources:
        for key, value in variables.items():
            ref = value.get("Ref") if isinstance(value, dict) else None
            if ref in tables:
                env[key] = tables[ref]
            elif ref in defaults:
                env[key] = str(parameters.get(ref, defaults[ref]))
            elif ref:
                env[key] = f"{ref}-TEST"   # 버킷처럼 여기서 만들지 않는 리소스
            else:
                env[key] = str(value)
    return env


def import_lambdas():
    """Lambda 코드를 새로 불러옵니다 (items.py, me.py는 불러올 때 환경변수의 테이블을 잡습니다)."""
    import importlib
    for directory in SRC_DIRS:
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    for name in LAMBDA_MODULES:
        sys.modules.pop(name, None)
    return {name: importlib.import_module(name) for name in LAMBDA_MODULES}


# ── 요청 만들기 ────────────────────────────────────────────────
def web_event(method, path, discord_user=None, email_user=None, body=None, query=None):
    """웹이 보낸 요청이 API Gateway(JWT Authorizer)를 지나 Lambda에 오는 모양."""
    context = {"http": {"method": method, "path": path}}
    if discord_user:
        claims = {"username": f"Discord_{discord_user}", "cognito:groups": "[us-east-1_TEST_Discord]"}
        context["authorizer"] = {"jwt": {"claims": claims}}
    elif email_user:
        context["authorizer"] = {"jwt": {"claims": {"username": email_user}}}
    return {
        "requestContext": context,
        "queryStringParameters": query,
        "body": json.dumps(body, ensure_ascii=False) if body is not None else None,
    }


def discord_event(payload, key=SIGNING_KEY, timestamp="1795500000"):
    """디스코드가 Interactions Endpoint로 보내는 서명된 요청."""
    body = json.dumps(payload, ensure_ascii=False)
    signature = key.sign(timestamp.encode() + body.encode("utf-8")).signature.hex()
    return {"headers": {"x-signature-ed25519": signature, "x-signature-timestamp": timestamp}, "body": body, "isBase64Encoded": False}


def slash(name, user_id, keyword=None):
    """서버에서 쓴 명령어 (/구독 키워드 등)."""
    data = {"name": name, "type": 1}
    if keyword is not None:
        data["options"] = [{"name": "키워드", "type": 3, "value": keyword}]
    return discord_event({"type": 2, "data": data, "member": {"user": {"id": user_id}}})


def body_of(response):
    return json.loads(response["body"])


# ── 가짜 디스코드 · Gemini ─────────────────────────────────────
class _Response:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, json.dumps(body, ensure_ascii=False)

    def json(self):
        return self._body


class FakeDiscord:
    """requests.Session 자리에 들어가는 가짜. 디스코드와 Gemini로 가는 요청만 받습니다."""
    CHANNELS = ("전북대", "충북대", "경북대", "부산대", "취업", "공모전", "트렌드")

    def __init__(self, channels=CHANNELS, roles=(), dm_blocked=()):
        self.channels = {name: f"80{i:016d}" for i, name in enumerate(channels)}
        self.roles = {name: f"70{i:016d}" for i, name in enumerate(roles)}   # 역할 이름 → ID
        self.dm_blocked = set(dm_blocked)       # DM을 막아 둔(또는 같은 서버에 없는) 사용자
        self.channel_messages = []              # [(채널 이름, 메시지)]
        self.dms = []                           # [(사용자 ID, 메시지)]
        self.gemini_calls = []                  # 요약 요청에 담긴 글 묶음
        self.violations = []                    # 디스코드라면 거부했을 메시지

    # 크롤러가 쓰는 두 가지 호출 모양
    def request(self, method, url, json=None, timeout=None, headers=None):
        if not url.startswith("https://discord.com/api/v10/"):
            raise AssertionError(f"예상하지 못한 주소: {url}")
        if (headers or {}).get("Authorization") != f"Bot {BOT_TOKEN}":
            return _Response(401, {"message": "401: Unauthorized"})
        path = url[len("https://discord.com/api/v10"):]

        if method == "GET" and path == f"/guilds/{GUILD_ID}/channels":
            return _Response(200, [{"id": cid, "name": name, "type": 0} for name, cid in self.channels.items()])
        if method == "GET" and path == f"/guilds/{GUILD_ID}/roles":
            return _Response(200, [{"id": rid, "name": name} for name, rid in self.roles.items()])
        if method == "POST" and path == "/users/@me/channels":
            return _Response(200, {"id": f"dm-{json['recipient_id']}"})
        match = re.fullmatch(r"/channels/([\w-]+)/messages", path)
        if method == "POST" and match:
            return self._message(match.group(1), json)
        return _Response(404, {"message": f"404: {method} {path}"})

    def post(self, url, json=None, timeout=None, headers=None):
        if "generativelanguage.googleapis.com" not in url:
            raise AssertionError(f"예상하지 못한 주소: {url}")
        entries = __import__("json").loads(json["contents"][0]["parts"][0]["text"])
        self.gemini_calls.append(entries)
        rows = [{"id": e["id"], "summary": ["12월 5일까지 온라인으로 접수함", "대학생이면 누구나 참여할 수 있음"], "fields": ["ai"]} for e in entries]
        text = __import__("json").dumps(rows, ensure_ascii=False)
        return _Response(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})

    def _message(self, channel_id, message):
        problems = check_message(message, set(self.roles.values()))
        if problems:
            self.violations.append((channel_id, problems))
            return _Response(400, {"message": "Invalid Form Body", "problems": problems})
        if channel_id.startswith("dm-"):
            user_id = channel_id[3:]
            if user_id in self.dm_blocked:
                return _Response(403, {"message": "Cannot send messages to this user", "code": 50007})
            self.dms.append((user_id, message))
        else:
            name = next((n for n, cid in self.channels.items() if cid == channel_id), None)
            if name is None:
                return _Response(404, {"message": "Unknown Channel", "code": 10003})
            self.channel_messages.append((name, message))
        return _Response(200, {"id": "1"})


def check_message(message, known_roles=()):
    """디스코드 메시지 한도 검사. 문제 목록을 돌려줍니다 (없으면 빈 목록)."""
    problems = []
    content, embeds = message.get("content", ""), message.get("embeds", [])
    if not content and not embeds:
        problems.append("내용이 비었음")
    if len(content) > 2000:
        problems.append(f"content {len(content)}자 > 2000")
    if len(embeds) > 10:
        problems.append(f"임베드 {len(embeds)}개 > 10")
    total = 0
    for embed in embeds:
        title, description, footer = embed.get("title", ""), embed.get("description", ""), embed.get("footer", {}).get("text", "")
        total += len(title) + len(description) + len(footer)
        if len(title) > 256 or len(description) > 4096 or len(footer) > 2048:
            problems.append(f"임베드 글자 수 한도 초과: {title[:30]}")
        if not str(embed.get("url", "")).startswith(("https://", "http://")):
            problems.append(f"임베드 주소가 http(s)가 아님: {embed.get('url')!r}")
    if total > 6000:
        problems.append(f"임베드 글자 합계 {total} > 6000")
    allowed = message.get("allowed_mentions")
    if allowed is None or allowed.get("parse") != []:
        problems.append("allowed_mentions가 없어 @everyone 등이 멘션될 수 있음")
    else:
        mentioned = set(re.findall(r"<@&(\d+)>", content))
        if mentioned - set(allowed.get("roles", [])):
            problems.append("allowed_mentions에 없는 역할을 멘션함")
        if known_roles and set(allowed.get("roles", [])) - set(known_roles):
            problems.append("서버에 없는 역할을 멘션함")
    return problems


# ── 환경 한 벌 ─────────────────────────────────────────────────
class Stack:
    """배포된 스택 흉내. with 블록 안에서만 유효합니다."""
    def __init__(self, discord=None, parameters=None):
        self.discord = discord or FakeDiscord()
        self.parameters = parameters
        self._saved_env, self._saved_session = {}, None

    def __enter__(self):
        import boto3
        import requests
        from moto import mock_aws

        self._mock = mock_aws()
        self._mock.start()
        fake_credentials = {"AWS_DEFAULT_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}
        self.template = load_template()
        try:
            self._set_env(fake_credentials)
            os.environ.pop("AWS_PROFILE", None)
            self.dynamodb = boto3.resource("dynamodb")
            self.table_names = create_tables(self.template, self.dynamodb)
            self._set_env(lambda_env(self.template, self.table_names, self.parameters))
            self.lambdas = import_lambdas()                 # crawler의 common.http는 여기서 진짜 Session을 잡음
            self._saved_session = requests.Session
            requests.Session = lambda: self.discord         # 그 뒤에 만드는 Session(디스코드·Gemini)은 가짜로
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _set_env(self, values):
        for key, value in values.items():
            self._saved_env.setdefault(key, os.environ.get(key))
            os.environ[key] = value

    def __exit__(self, *exc):
        import requests
        if self._saved_session is not None:
            requests.Session = self._saved_session
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._mock.stop()
        return False

    def table(self, logical):
        return self.dynamodb.Table(self.table_names[logical])

    def scan(self, logical):
        table, rows, kwargs = self.table(logical), [], {}
        while True:
            res = table.scan(**kwargs)
            rows.extend(res["Items"])
            if "LastEvaluatedKey" not in res:
                return rows
            kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]

    # Lambda 호출
    def crawl(self):
        """크롤러 Lambda 한 번 실행 (EventBridge가 부르는 것과 같음). 결과 통계를 돌려줍니다."""
        return body_of(self.lambdas["handler"].lambda_handler({}, None))

    def web(self, method, path, **kwargs):
        module = self.lambdas["items" if path == "/items" else "me"]
        res = module.lambda_handler(web_event(method, path, **kwargs), None)
        return res["statusCode"], body_of(res)

    def bot(self, name, user_id, keyword=None):
        """명령어를 쓰고 답장 글을 돌려줍니다."""
        res = self.lambdas["interactions"].lambda_handler(slash(name, user_id, keyword), None)
        assert res["statusCode"] == 200, res
        return body_of(res)["data"]["content"]
