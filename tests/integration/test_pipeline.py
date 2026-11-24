"""전체 파이프라인 통합 테스트.

  디스코드 명령어 ─▶ bot Lambda ─┐
  웹 키워드 알림 ─▶ me Lambda ──┴▶ 구독 테이블 ─┐
  크롤러 Lambda ─▶ 글 테이블 ─▶ items Lambda(웹)  ├▶ 디스코드 채널 게시 · 구독 DM
                └──────────────────────────────┘

영역마다 따로 있는 테스트는 각자의 코드만 봅니다. 여기서는 Lambda 4개를 infra/template.yaml대로 만든
테이블에 붙여, 한쪽에서 쓴 것을 다른 쪽이 읽을 수 있는지 봅니다.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import harness

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
OLD = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

MINSU, JIWOO, BLOCKED = "100000000000000001", "100000000000000002", "100000000000000003"


def item(id, category, subtype, title, date=TODAY, **over):
    return {"id": id, "category": category, "subtype": subtype, "source": f"{subtype} 출처", "title": title,
            "fields": [], "date": date, "url": f"https://example.com/{id}", **over}


class Site:
    """수집기 흉내. posts를 바꾸면 사이트에 새 글이 올라온 것입니다."""
    def __init__(self, *posts):
        self.posts = list(posts)
        self.body_requests = []

    def fetch(self):
        return [dict(p) for p in self.posts]

    def fetch_body(self, it):
        self.body_requests.append(it["id"])
        return "본문 내용"


@pytest.fixture
def stack():
    discord = harness.FakeDiscord(
        channels=("전북대", "취업", "공모전", "트렌드"),          # 충북대 채널은 아직 안 만든 서버
        roles=("@everyone", "운영진", "알림-해커톤"),
        dm_blocked={BLOCKED},
    )
    with harness.Stack(discord) as stack:
        stack.lambdas["handler"].BODY_PAUSE = 0
        yield stack


def test_whole_pipeline(stack, monkeypatch):
    handler, discord = stack.lambdas["handler"], stack.discord
    jbnu = Site(item("jbnu-1", "univ", "전북대", "2학기 기말고사 일정 안내"))
    cbnu = Site(item("cbnu-1", "univ", "충북대", "도서관 휴관 안내"))
    devevent = Site(item("devevent-1", "contest", "해커톤", "가을 해커톤 참가자 모집", deadline=TODAY))
    monkeypatch.setattr(handler, "SOURCES", [jbnu, cbnu, devevent])

    # ── 1. 구독: 디스코드와 웹에서 넣은 키워드가 한 목록이 된다 ──────────
    assert "구독을 시작했어요" in stack.bot("구독", MINSU, "해커톤")
    status, res = stack.web("PUT", "/me/subscriptions", discord_user=MINSU, body={"keyword": "장학금"})
    assert (status, res) == (200, {"userId": MINSU, "keywords": ["장학금", "해커톤"]})   # 봇에서 넣은 것도 웹에 보임
    assert "`장학금`, `해커톤`" in stack.bot("목록", MINSU)                                # 웹에서 넣은 것도 봇에 보임
    stack.web("PUT", "/me/subscriptions", discord_user=JIWOO, body={"keyword": "인턴"})
    stack.bot("구독", BLOCKED, "인턴")
    assert sorted((r["userId"], r["keyword"]) for r in stack.scan("SubscriptionsTable")) == [
        (MINSU, "장학금"), (MINSU, "해커톤"), (JIWOO, "인턴"), (BLOCKED, "인턴")]
    # 이메일로 로그인한 사용자는 DM을 받을 수 없으므로 구독 API를 못 쓴다
    assert stack.web("GET", "/me/subscriptions", email_user="someone@example.com")[0] == 403

    # ── 2. 첫 실행(처음 배포): 이미 있던 글은 저장만 하고 알리지 않는다 ──
    stats = stack.crawl()
    assert (stats["collected"], stats["new"], stats["saved"], stats["quiet"]) == (3, 3, 3, 3)
    assert stats["summarized"] == 3
    assert discord.channel_messages == [] and discord.dms == []
    status, res = stack.web("GET", "/items")
    assert status == 200 and {it["id"] for it in res["items"]} == {"jbnu-1", "cbnu-1", "devevent-1"}
    assert all(it["summary"] and it["fields"] == ["ai"] for it in res["items"])   # 요약·분야 태그가 웹까지 감

    # ── 3. 새 글이 올라옴: 저장 → 채널 게시 → 구독자 DM ────────────────
    jbnu.posts += [
        item("jbnu-2", "univ", "전북대", "[학생과] 국가장학금 2차 신청 안내"),
        item("jbnu-3", "univ", "전북대", "지난 학기 장학금 수혜 내역", date=OLD),      # 게시일이 오래됨 → 저장만
    ]
    cbnu.posts.append(item("cbnu-2", "univ", "충북대", "충북대 해커톤 설명회"))         # 채널이 없는 학교
    devevent.posts.append(item("devevent-2", "contest", "해커톤", "겨울 오픈소스 해커톤 @everyone", deadline=TODAY))
    jumpit = Site(item("jumpit-1", "jobs", "인턴", "백엔드 인턴 채용"))                 # 나중에 붙인 사이트 → 밀린 글
    handler.SOURCES.append(jumpit)

    stats = stack.crawl()
    assert (stats["collected"], stats["existing"], stats["new"], stats["saved"], stats["quiet"]) == (8, 3, 5, 5, 1)
    assert stats["channels"] == {"posted": 2, "messages": 2, "noChannel": 1, "failed": 0}
    assert stats["notify"] == {"users": 1, "sent": 1, "failed": 0}

    posts = {name: message for name, message in discord.channel_messages}
    assert set(posts) == {"전북대", "공모전"}
    assert [e["title"] for e in posts["전북대"]["embeds"]] == ["\\[학생과\\] 국가장학금 2차 신청 안내"]
    assert posts["전북대"]["content"] == ""                               # 맞는 키워드 역할이 없으면 멘션 없음
    contest = posts["공모전"]
    hackathon_role = discord.roles["알림-해커톤"]
    assert contest["content"] == f"<@&{hackathon_role}>"                  # "알림-해커톤" 역할만 멘션
    assert contest["allowed_mentions"] == {"parse": [], "roles": [hackathon_role]}   # 제목의 @everyone은 멘션 안 됨
    assert contest["embeds"][0]["url"] == "https://example.com/devevent-2"
    assert "12월 5일까지 온라인으로 접수함" in contest["embeds"][0]["description"]   # 요약이 카드에 들어감
    assert f"마감 {TODAY}" in contest["embeds"][0]["footer"]["text"]

    assert [user for user, _ in discord.dms] == [MINSU]                   # 한 사람에게 한 통으로 묶어서
    dm = discord.dms[0][1]["content"]
    assert "새 글 3건" in dm
    assert all(url in dm for url in ("<https://example.com/jbnu-2>", "<https://example.com/cbnu-2>", "<https://example.com/devevent-2>"))
    assert "jbnu-3" not in dm and "jumpit-1" not in dm                    # 오래된 글, 밀린 글은 알리지 않음
    assert discord.dms[0][1]["allowed_mentions"] == {"parse": []}

    # 웹에는 알리지 않은 글까지 모두 보인다
    status, res = stack.web("GET", "/items")
    assert len(res["items"]) == 8 and res["items"][-1]["id"] == "jbnu-3"   # 최신순
    status, res = stack.web("GET", "/items", query={"category": "jobs"})
    assert [it["id"] for it in res["items"]] == ["jumpit-1"]
    assert stack.web("GET", "/items", query={"category": "etc"})[0] == 400

    # ── 4. 같은 글로 한 번 더: 다시 저장·게시·알림하지 않는다 ────────────
    sent_before = (len(discord.channel_messages), len(discord.dms), len(discord.gemini_calls))
    stats = stack.crawl()
    assert (stats["existing"], stats["new"], stats["saved"]) == (8, 0, 0)
    assert (len(discord.channel_messages), len(discord.dms), len(discord.gemini_calls)) == sent_before
    assert len(stack.scan("ItemsTable")) == 8

    # ── 5. 해지하면 다음 글부터 DM이 안 온다. 한 사람이 DM을 막아 둬도 나머지는 받는다 ──
    assert "해지했어요" in stack.bot("해지", MINSU, "해커톤")
    assert stack.web("GET", "/me/subscriptions", discord_user=MINSU)[1]["keywords"] == ["장학금"]
    devevent.posts.append(item("devevent-3", "contest", "해커톤", "신년 해커톤 참가팀 모집"))
    jumpit.posts.append(item("jumpit-2", "jobs", "인턴", "데이터 엔지니어 인턴"))

    stats = stack.crawl()
    assert (stats["new"], stats["saved"], stats["quiet"]) == (2, 2, 0)
    assert stats["channels"] == {"posted": 2, "messages": 2, "noChannel": 0, "failed": 0}
    assert stats["notify"] == {"users": 2, "sent": 1, "failed": 1}        # BLOCKED는 실패, JIWOO는 받음
    assert [user for user, _ in discord.dms] == [MINSU, JIWOO]
    assert "데이터 엔지니어 인턴" in discord.dms[1][1]["content"] and "해커톤" not in discord.dms[1][1]["content"]
    assert [name for name, _ in discord.channel_messages[2:]] == ["공모전", "취업"]

    # ── 끝. 디스코드가 거부했을 메시지가 없고, 본문은 새 글에만 한 번씩 요청했다 ──
    assert discord.violations == []
    assert sorted(jbnu.body_requests) == ["jbnu-1", "jbnu-2", "jbnu-3"]


def test_without_tokens_only_saves(monkeypatch):
    """토큰·키 없이 배포하면(파라미터 기본값) 수집·저장·목록 API만 동작하고 나머지는 조용히 꺼진다."""
    off = {"DiscordBotToken": "", "DiscordGuildId": "", "GeminiApiKey": "", "DiscordPublicKey": ""}
    with harness.Stack(parameters=off) as stack:
        handler = stack.lambdas["handler"]
        site = Site(item("jbnu-1", "univ", "전북대", "공지"))
        monkeypatch.setattr(handler, "SOURCES", [site])
        stack.crawl()
        site.posts.append(item("jbnu-2", "univ", "전북대", "새 공지"))
        stats = stack.crawl()
        assert (stats["saved"], stats["summarized"]) == (1, 0)
        assert stats["channels"]["posted"] == 0 and stats["notify"]["sent"] == 0
        assert site.body_requests == []   # 요약이 꺼져 있으면 본문 페이지도 읽지 않음
        assert len(stack.web("GET", "/items")[1]["items"]) == 2
        assert "summary" not in stack.web("GET", "/items")[1]["items"][0]
        # 공개 키가 없으면 봇 명령어 요청은 전부 거부
        res = stack.lambdas["interactions"].lambda_handler(harness.slash("목록", MINSU), None)
        assert res["statusCode"] == 401
        assert stack.discord.channel_messages == [] and stack.discord.dms == []


def test_bot_and_web_share_the_same_rules(stack):
    """봇(bot/src/subscriptions.py)과 웹(api/src/me.py)의 구독 규칙이 같아야 한 목록을 쓸 수 있다."""
    import subscriptions
    me = stack.lambdas["me"]
    assert (subscriptions.MAX_KEYWORDS, subscriptions.MAX_LENGTH) == (me.MAX_KEYWORDS, me.MAX_LENGTH)
    for raw in ("해커톤", "  겨울   해커톤 ", "", "   ", "가" * 30, "가" * 31, None, 5):
        assert subscriptions.clean_keyword(raw) == me.clean_keyword(raw)

    # 웹에서 20개를 채우면 봇에서도 더 못 넣는다
    for i in range(me.MAX_KEYWORDS):
        assert stack.web("PUT", "/me/subscriptions", discord_user=MINSU, body={"keyword": f"키워드{i}"})[0] == 200
    assert "20개까지" in stack.bot("구독", MINSU, "하나 더")
    assert stack.web("PUT", "/me/subscriptions", discord_user=MINSU, body={"keyword": "하나 더"})[0] == 400
    # 봇에서 지우면 웹에서 다시 넣을 수 있다
    stack.bot("해지", MINSU, "키워드0")
    status, res = stack.web("PUT", "/me/subscriptions", discord_user=MINSU, body={"keyword": "하나 더"})
    assert status == 200 and len(res["keywords"]) == 20 and "키워드0" not in res["keywords"]
    # 웹에서 지운 것은 봇 목록에서도 빠진다
    stack.web("DELETE", "/me/subscriptions", discord_user=MINSU, query={"keyword": "하나 더"})
    assert "하나 더" not in stack.bot("목록", MINSU)


def test_template_matches_code():
    """template.yaml의 Lambda마다 CodeUri·Handler가 실제 파일·함수를 가리키고, 묶음에 넣을 패키지 목록이 있다."""
    template = harness.load_template()
    functions = {name: r["Properties"] for name, r in template["Resources"].items() if r["Type"] == "AWS::Serverless::Function"}
    assert set(functions) == {"CrawlerFunction", "ItemsApiFunction", "MeApiFunction", "ProfileApiFunction", "ChatApiFunction", "BotFunction"}
    for name, props in functions.items():
        code = (harness.TEMPLATE.parent / props["CodeUri"]).resolve()
        module, function = props["Handler"].split(".")
        assert (code / f"{module}.py").is_file(), f"{name}: {module}.py 없음"
        assert f"def {function}(event, context)" in (code / f"{module}.py").read_text(encoding="utf-8"), name
        requirements = code / "requirements.txt"
        assert requirements.is_file() and requirements.read_text(encoding="utf-8").isascii(), f"{name}: requirements.txt"
        assert props["Role"] == {"Sub": "arn:aws:iam::${AWS::AccountId}:role/LabRole"}, f"{name}: Learner Lab은 LabRole만"

    # 디스코드가 부르는 주소는 로그인 없이 열려 있어야 하고(서명으로 검사), Outputs의 주소와 경로가 같아야 한다
    event = functions["BotFunction"]["Events"]["Interactions"]["Properties"]
    assert (event["Path"], event["Method"]) == ("/discord/interactions", "POST") and "Auth" not in event
    assert template["Outputs"]["DiscordInteractionsUrl"]["Value"]["Sub"].endswith(event["Path"])
    assert "PyNaCl" in (Path(harness.ROOT) / "bot" / "src" / "requirements.txt").read_text(encoding="utf-8")
