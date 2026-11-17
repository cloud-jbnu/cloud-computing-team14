from datetime import datetime, timedelta

import pytest

import channels
import notify

TODAY = datetime.now(notify.KST).strftime("%Y-%m-%d")
OLD = (datetime.now(notify.KST) - timedelta(days=30)).strftime("%Y-%m-%d")


def make(id, category="univ", subtype="전북대", title=None, **over):
    item = {"id": id, "category": category, "subtype": subtype, "source": "출처", "title": title or f"{id} 제목",
            "date": TODAY, "url": f"https://example.com/{id}", "fields": []}
    item.update(over)
    return item


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class FakeDiscord:
    """디스코드 REST API 흉내: 채널·역할 목록을 돌려주고, 보낸 메시지를 기록합니다."""
    def __init__(self, channel_names, roles=(), fail_channels=(), fail_roles=False):
        self.channels = [{"id": f"ch-{name}", "name": name, "type": 0} for name in channel_names]
        self.channels.append({"id": "voice", "name": "취업", "type": 2})   # 음성 채널은 무시해야 함
        self.roles = [{"id": role_id, "name": name} for name, role_id in roles]
        self.fail_channels, self.fail_roles = set(fail_channels), fail_roles
        self.sent = []   # (채널 ID, 메시지)

    def request(self, method, url, json=None, timeout=None, headers=None):
        assert headers["Authorization"] == "Bot 토큰"
        path = url.replace(notify.API, "")
        if method == "GET" and path == "/guilds/서버/channels":
            return FakeResponse(200, self.channels)
        if method == "GET" and path == "/guilds/서버/roles":
            return FakeResponse(403, {"message": "권한 없음"}) if self.fail_roles else FakeResponse(200, self.roles)
        if method == "POST" and path.endswith("/messages"):
            channel_id = path.split("/")[2]
            if channel_id in self.fail_channels:
                return FakeResponse(403, {"message": "Missing Permissions"})
            self.sent.append((channel_id, json))
            return FakeResponse(200, {"id": "메시지"})
        raise AssertionError(f"예상하지 못한 요청: {method} {path}")


def post(items, discord):
    return channels.post(items, token="토큰", guild_id="서버", session=discord)


# ── 채널 고르기 ───────────────────────────────────────────────
@pytest.mark.parametrize("item, expected", [
    (make("a", "univ", "전북대"), "전북대"),
    (make("a", "univ", "부산대"), "부산대"),
    (make("a", "jobs", "신입"), "취업"),
    (make("a", "contest", "해커톤"), "공모전"),
    (make("a", "tech", "GitHub"), "트렌드"),
])
def test_channel_name(item, expected):
    assert channels.channel_name(item) == expected


def test_load_channels_ignores_non_text_channels():
    discord = FakeDiscord(["전북대", "취업"])
    assert channels.load_channels(discord, "토큰", "서버") == {"전북대": "ch-전북대", "취업": "ch-취업"}


# ── 역할 멘션 ─────────────────────────────────────────────────
def test_load_roles_takes_only_prefixed_roles():
    discord = FakeDiscord([], roles=[("알림-해커톤", "1"), ("관리자", "2"), ("알림-", "3"), ("알림- AI ", "4"), ("@everyone", "5")])
    assert channels.load_roles(discord, "토큰", "서버") == [("해커톤", "1"), ("AI", "4")]


def test_matched_roles_looks_at_title_and_summary():
    roles = [("해커톤", "1"), ("ai", "2"), ("장학금", "3")]
    item = make("a", title="겨울 해커톤 참가팀 모집", summary=["AI 서비스를 주제로 함"])
    assert channels.matched_roles(item, roles) == ["1", "2"]
    assert channels.matched_roles(make("b", title="수강신청 안내"), roles) == []


# ── 메시지 만들기 ─────────────────────────────────────────────
def test_build_embed():
    item = make("a", "contest", "해커톤", title="*겨울* 해커톤", source="주최", deadline="2026-12-05",
                summary=["3~4인 팀으로 참가함", "12월 5일까지 접수함"])
    embed = channels.build_embed(item)
    assert embed["title"] == "\\*겨울\\* 해커톤"            # 마크다운 기호는 서식이 되지 않게 막음
    assert embed["url"] == "https://example.com/a"
    assert embed["description"] == "• 3\\~4인 팀으로 참가함\n• 12월 5일까지 접수함"   # ~도 취소선이 되지 않게 막음
    assert embed["footer"]["text"] == "주최 · 마감 2026-12-05"


def test_build_embed_without_summary_and_with_repo():
    embed = channels.build_embed(make("a", "tech", "GitHub", source="GitHub Trending", repo={"lang": "Go", "starsToday": 412}))
    assert "description" not in embed
    assert embed["footer"]["text"] == "GitHub Trending · Go · ★ 412 today"


def test_build_messages_splits_by_embed_count():
    messages = channels.build_messages([make(f"a-{i}") for i in range(23)], [])
    assert [len(m["embeds"]) for m in messages] == [10, 10, 3]


def test_build_messages_splits_by_total_length():
    long = [make(f"a-{i}", title="가" * 240, summary=["나" * 120] * 3) for i in range(10)]
    messages = channels.build_messages(long, [])
    assert len(messages) > 1
    for m in messages:
        assert sum(channels._size(e) for e in m["embeds"]) <= channels.MAX_EMBED_CHARS


def test_build_messages_mentions_only_matching_roles_per_message():
    roles = [("해커톤", "1"), ("장학금", "2")]
    items = [make(f"a-{i}") for i in range(10)] + [make("b", title="겨울 해커톤 모집 @everyone")]
    first, second = channels.build_messages(items, roles)
    assert first["content"] == "" and first["allowed_mentions"] == {"parse": [], "roles": []}
    assert second["content"] == "<@&1>"
    assert second["allowed_mentions"] == {"parse": [], "roles": ["1"]}   # @everyone은 멘션되지 않음


# ── 게시 ──────────────────────────────────────────────────────
def test_post_routes_items_to_channels():
    discord = FakeDiscord(["전북대", "충북대", "취업", "공모전", "트렌드"], roles=[("알림-해커톤", "9")])
    items = [
        make("jbnu-1", "univ", "전북대"), make("jbnu-2", "univ", "전북대"), make("cbnu-1", "univ", "충북대"),
        make("jumpit-1", "jobs", "신입"), make("devevent-1", "contest", "해커톤", title="겨울 해커톤"), make("github-1", "tech", "GitHub"),
    ]
    stats = post(items, discord)
    assert stats == {"posted": 6, "messages": 5, "noChannel": 0, "failed": 0}
    sent = {channel: [e["url"].rsplit("/", 1)[1] for e in message["embeds"]] for channel, message in discord.sent}
    assert sent == {
        "ch-전북대": ["jbnu-1", "jbnu-2"], "ch-충북대": ["cbnu-1"], "ch-취업": ["jumpit-1"],
        "ch-공모전": ["devevent-1"], "ch-트렌드": ["github-1"],
    }
    contest = dict(discord.sent)["ch-공모전"]
    assert contest["content"] == "<@&9>" and contest["allowed_mentions"]["roles"] == ["9"]


def test_post_skips_old_items():
    discord = FakeDiscord(["전북대"])
    stats = post([make("jbnu-1", date=OLD), make("jbnu-2")], discord)
    assert stats["posted"] == 1 and len(discord.sent[0][1]["embeds"]) == 1


def test_post_missing_channel_is_counted_not_fatal():
    discord = FakeDiscord(["전북대"])
    stats = post([make("jbnu-1"), make("knu-1", "univ", "경북대"), make("knu-2", "univ", "경북대")], discord)
    assert stats == {"posted": 1, "messages": 1, "noChannel": 2, "failed": 0}


def test_post_channel_failure_does_not_stop_others():
    discord = FakeDiscord(["전북대", "취업"], fail_channels=["ch-전북대"])
    stats = post([make("jbnu-1"), make("jumpit-1", "jobs", "신입")], discord)
    assert stats == {"posted": 1, "messages": 1, "noChannel": 0, "failed": 1}


def test_post_without_roles_permission_still_posts():
    discord = FakeDiscord(["전북대"], fail_roles=True)
    assert post([make("jbnu-1")], discord)["posted"] == 1


@pytest.mark.parametrize("token, guild", [("", "서버"), ("토큰", "")])
def test_post_without_config_does_nothing(token, guild):
    discord = FakeDiscord(["전북대"])
    stats = channels.post([make("jbnu-1")], token=token, guild_id=guild, session=discord)
    assert stats["posted"] == 0 and discord.sent == []


def test_post_nothing_recent_makes_no_request():
    class NoRequests:
        def request(self, *a, **k):
            raise AssertionError("요청하면 안 됨")
    assert channels.post([make("jbnu-1", date=OLD)], token="토큰", guild_id="서버", session=NoRequests())["posted"] == 0
