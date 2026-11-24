from datetime import datetime

import notify

TODAY = datetime.now(notify.KST).strftime("%Y-%m-%d")


def item(id, category, subtype, title):
    return {"id": id, "category": category, "subtype": subtype, "source": subtype, "title": title,
            "date": TODAY, "url": f"https://example.com/{id}"}


ITEMS = [
    item("jbnu-1", "univ", "전북대", "전북대 해커톤 참가 안내"),
    item("knu-1", "univ", "경북대", "경북대 해커톤 설명회"),
    item("devevent-1", "contest", "해커톤", "겨울 해커톤 참가자 모집"),
]


class FakeTable:
    def __init__(self, rows):
        self.rows = rows

    def scan(self, **_):
        return {"Items": self.rows}


class FakeSession:
    """디스코드 REST API 대신: 보낸 DM을 사용자별로 적어 둡니다."""
    def __init__(self):
        self.sent, self._channel = {}, {}

    def request(self, method, url, json=None, **_):
        class Res:
            status_code = 200

            def __init__(self, body):
                self._body = body

            def json(self):
                return self._body
        if url.endswith("/users/@me/channels"):
            self._channel[f"ch-{json['recipient_id']}"] = json["recipient_id"]
            return Res({"id": f"ch-{json['recipient_id']}"})
        channel = url.split("/channels/")[1].split("/")[0]
        self.sent[self._channel[channel]] = json["content"]
        return Res({})


def test_only_my_school_drops_other_schools_notices():
    targets = notify.match(ITEMS, {"해커톤": {"a", "b", "c"}})
    result = notify.only_my_school(targets, {"a": "전북대", "b": "other"})
    assert [it["id"] for it, _ in result["a"]] == ["jbnu-1", "devevent-1"]      # 내 학교 + 학교 밖 글
    assert [it["id"] for it, _ in result["b"]] == ["devevent-1"]                 # 목록에 없는 학교: 학교 공지 없음
    assert [it["id"] for it, _ in result["c"]] == ["jbnu-1", "knu-1", "devevent-1"]   # 학교 안 정함: 예전처럼 모두


def test_user_left_with_nothing_is_dropped():
    targets = notify.match(ITEMS[:2], {"해커톤": {"a"}})
    assert notify.only_my_school(targets, {"a": "부산대"}) == {}


def test_load_schools_reads_discord_users_only():
    table = FakeTable([
        {"discordId": "1", "school": "전북대"},
        {"school": "경북대"},                         # 이메일 사용자 (디스코드 ID 없음)
        {"discordId": "2", "school": "other"},
    ])
    assert notify.load_schools(table) == {"1": "전북대", "2": "other"}


def test_notify_sends_only_my_school(monkeypatch):
    subs = FakeTable([{"userId": "1", "keyword": "해커톤"}, {"userId": "2", "keyword": "해커톤"}])
    profiles = FakeTable([{"discordId": "1", "school": "경북대"}])
    session = FakeSession()
    stats = notify.notify(ITEMS, table=subs, token="토큰", session=session, profiles_table=profiles)
    assert stats == {"users": 2, "sent": 2, "failed": 0}
    assert "경북대 해커톤" in session.sent["1"] and "전북대 해커톤" not in session.sent["1"]
    assert "전북대 해커톤" in session.sent["2"] and "경북대 해커톤" in session.sent["2"]


def test_notify_keeps_working_when_profiles_unreadable():
    class Broken:
        def scan(self, **_):
            raise RuntimeError("테이블 없음")

    subs = FakeTable([{"userId": "1", "keyword": "해커톤"}])
    session = FakeSession()
    stats = notify.notify(ITEMS, table=subs, token="토큰", session=session, profiles_table=Broken())
    assert stats["sent"] == 1 and "전북대 해커톤" in session.sent["1"]
