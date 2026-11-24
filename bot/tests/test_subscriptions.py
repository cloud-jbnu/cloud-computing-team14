import subscriptions

ME, OTHER = "111", "222"


def test_clean_keyword():
    assert subscriptions.clean_keyword("  겨울   해커톤 ") == "겨울 해커톤"
    assert subscriptions.clean_keyword("   ") is None
    assert subscriptions.clean_keyword("가" * (subscriptions.MAX_LENGTH + 1)) is None
    assert subscriptions.clean_keyword(None) is None
    assert subscriptions.clean_keyword(123) is None


def test_subscribe_list_unsubscribe(table):
    assert "구독한 키워드가 없어요" in subscriptions.reply(table, "목록", ME)
    assert "구독을 시작했어요" in subscriptions.reply(table, "구독", ME, " 해커톤 ")
    assert "이미 구독 중" in subscriptions.reply(table, "구독", ME, "해커톤")
    subscriptions.reply(table, "구독", ME, "CTF")
    subscriptions.reply(table, "구독", OTHER, "장학금")
    assert table.rows == {(ME, "해커톤"), (ME, "CTF"), (OTHER, "장학금")}

    listing = subscriptions.reply(table, "목록", ME)
    assert "2개" in listing and "`CTF`, `해커톤`" in listing and "장학금" not in listing   # 내 것만, 가나다순

    assert "해지했어요" in subscriptions.reply(table, "해지", ME, "해커톤")
    assert "구독하고 있지 않아요" in subscriptions.reply(table, "해지", ME, "해커톤")
    assert "구독하고 있지 않아요" in subscriptions.reply(table, "해지", ME, "장학금")   # 남의 구독은 못 지움
    assert table.rows == {(ME, "CTF"), (OTHER, "장학금")}


def test_rejects_bad_keyword(table):
    for bad in ("", "   ", "가" * 31, None):
        assert "1~30자" in subscriptions.reply(table, "구독", ME, bad)
        assert "1~30자" in subscriptions.reply(table, "해지", ME, bad)
    assert table.rows == set()


def test_limit(table):
    for i in range(subscriptions.MAX_KEYWORDS):
        assert subscriptions.add(table, ME, f"k{i}") == "added"
    assert "20개까지" in subscriptions.reply(table, "구독", ME, "하나 더")
    assert subscriptions.add(table, ME, "k0") == "exists"      # 꽉 찼어도 이미 있는 건 오류가 아님
    assert subscriptions.add(table, OTHER, "하나 더") == "added"  # 한도는 사용자마다
    assert len(table.rows) == subscriptions.MAX_KEYWORDS + 1


def test_backtick_in_keyword_does_not_break_reply(table):
    assert "`a'b`" in subscriptions.reply(table, "구독", ME, "a`b")
    assert (ME, "a`b") in table.rows   # 저장은 입력한 그대로


def test_unknown_command(table):
    assert "모르는 명령어" in subscriptions.reply(table, "삭제", ME, "x")


def test_suggest(table):
    for kw in ("해커톤", "AI 해커톤", "ctf"):
        subscriptions.add(table, ME, kw)
    assert subscriptions.suggest(table, ME) == ["AI 해커톤", "ctf", "해커톤"]
    assert subscriptions.suggest(table, ME, "해커") == ["AI 해커톤", "해커톤"]
    assert subscriptions.suggest(table, ME, "CTF") == ["ctf"]   # 대소문자 무시
    assert subscriptions.suggest(table, OTHER) == []
