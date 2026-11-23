"""실제 사이트에서 수집한 글로 전체 파이프라인을 한 번 돌려 보고 결과를 출력합니다.

AWS 계정·디스코드 토큰 없이 돕니다. 진짜인 것은 사이트 수집뿐이고, DynamoDB는 moto, 디스코드는 가짜입니다
(harness.py). 가짜 디스코드는 받은 메시지를 디스코드 한도로 검사하므로, 실제 글 제목·길이로도 메시지가
거부되지 않는지 볼 수 있습니다. AI 요약은 키가 없어 꺼진 채로 돕니다.

  1. 구독     봇 명령어와 웹 API로 키워드를 넣습니다.
  2. 첫 배포  밀린 글이 다 저장될 때까지 크롤러를 여러 번 돌립니다 (게시·알림이 없어야 함).
  3. 재실행   사이트를 다시 읽어 같은 글이 또 저장되지 않는지 봅니다.
  4. 새 글    최근 글 몇 건을 "방금 올라온 글"로 되돌린 뒤 돌려, 채널 게시와 DM을 확인합니다.
  5. 목록 API 웹이 받는 GET /items를 확인합니다.

실행: 저장소 맨 위에서  python tests/integration/run_live.py [결과를 저장할 .json 경로]
사이트마다 목록을 두 번(2·3단계) 읽습니다. 연달아 여러 번 돌리지 마세요.
"""
import json
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import harness

KST = timezone(timedelta(hours=9))
USER = "100000000000000001"
KEYWORDS_BOT = ["해커톤", "장학금", "인턴"]     # 디스코드 명령어로 넣을 키워드
KEYWORDS_WEB = ["AI", "채용"]                  # 웹에서 넣을 키워드
ROLES = ("알림-해커톤", "알림-장학금", "알림-인턴", "알림-AI")
NEW_PER_CATEGORY = 3                           # 4단계에서 카테고리마다 새 글로 되돌릴 글 수


def site_of(item_id):
    return item_id.split("-", 1)[0]


def make_new_again(stack, items):
    """저장된 글을 '아직 못 본 새 글'로 되돌립니다: 글을 지우고, 밀린 글 목록에서도 뺍니다."""
    for it in items:
        stack.table("ItemsTable").delete_item(Key={"id": it["id"]})
        stack.table("SeenTable").update_item(
            Key={"seenKey": f"source#{site_of(it['id'])}"},
            UpdateExpression="DELETE backlogIds :ids", ExpressionAttributeValues={":ids": {it["id"]}},
        )


def pick_recent(items, keywords):
    """카테고리마다 최근(3일 안) 글을 고릅니다. 구독 키워드가 들어간 글을 먼저."""
    today = datetime.now(KST).date()
    picked = []
    for category in ("univ", "contest", "jobs", "tech"):
        recent = [it for it in items if it["category"] == category
                  and (today - datetime.strptime(it["date"], "%Y-%m-%d").date()).days <= 3]
        text = lambda it: f"{it['title']} {it['source']} {it['subtype']}".lower()
        recent.sort(key=lambda it: not any(k.lower() in text(it) for k in keywords))
        picked += recent[:NEW_PER_CATEGORY]
    return picked


def main(out_path=None):
    report = {"date": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "steps": {}}
    discord = harness.FakeDiscord(roles=("@everyone",) + ROLES)
    with harness.Stack(discord, parameters={"GeminiApiKey": ""}) as stack:
        handler = stack.lambdas["handler"]
        real_collect = handler.collect
        cache = {}

        def collect_once(label):
            """사이트는 단계마다 한 번만 읽고, 그 단계 안의 반복 실행은 읽어 둔 글을 다시 씁니다."""
            if label not in cache:
                started = time.time()
                cache[label] = real_collect()
                cache[label + "_seconds"] = round(time.time() - started, 1)
            return [dict(raw) if isinstance(raw, dict) else raw for raw in cache[label]]

        # 1. 구독
        for kw in KEYWORDS_BOT:
            stack.bot("구독", USER, kw)
        for kw in KEYWORDS_WEB:
            stack.web("PUT", "/me/subscriptions", discord_user=USER, body={"keyword": kw})
        listing = stack.bot("목록", USER)
        web_listing = stack.web("GET", "/me/subscriptions", discord_user=USER)[1]["keywords"]
        report["steps"]["1_subscribe"] = {"bot": KEYWORDS_BOT, "web": KEYWORDS_WEB, "bot_list_reply": listing,
                                          "web_list": web_listing,
                                          "ok": sorted(web_listing) == sorted(KEYWORDS_BOT + KEYWORDS_WEB)
                                          and all(k in listing for k in KEYWORDS_WEB)}

        # 2. 첫 배포: 밀린 글 저장
        handler.collect = lambda: collect_once("first")
        runs = []
        for _ in range(15):
            stats = stack.crawl()
            runs.append(stats)
            if not stats["deferred"]:
                break
        raw = cache["first"]
        per_source = Counter(site_of(r["id"]) for r in raw if isinstance(r, dict))
        failed_sources = [s.__name__ for s in handler.SOURCES if s not in {r.get("_module") for r in raw if isinstance(r, dict)}]
        stored = stack.scan("ItemsTable")
        report["steps"]["2_first_deploy"] = {
            "collect_seconds": cache["first_seconds"], "collected": len(raw), "per_source": dict(per_source),
            "sources_without_items": failed_sources, "runs": len(runs),
            "saved_per_run": [r["saved"] for r in runs], "invalid": runs[0]["invalid"],
            "dup_in_run": runs[0]["dupInRun"], "dup_cross_site": runs[0]["dupCrossSite"],
            "stored": len(stored), "per_category": dict(Counter(it["category"] for it in stored)),
            "channel_messages": len(discord.channel_messages), "dms": len(discord.dms),
            "ok": not runs[-1]["deferred"] and len(stored) == runs[0]["new"] and not discord.channel_messages and not discord.dms,
        }

        # 3. 재실행: 사이트를 다시 읽어도 같은 글이 또 들어가지 않음
        handler.collect = lambda: collect_once("second")
        stats = stack.crawl()
        arrived = [it for it in stack.scan("ItemsTable") if it["id"] not in {s["id"] for s in stored}]
        report["steps"]["3_rerun"] = {
            "collected": stats["collected"], "existing": stats["existing"], "new": stats["new"], "saved": stats["saved"],
            "new_titles": [it["title"] for it in arrived],   # 두 번 읽는 사이에 실제로 올라온 글 (있으면 정상 게시됨)
            "ok": stats["saved"] == stats["new"] == len(arrived) and stats["existing"] >= len(stored) - 5,
        }
        sent_before = (len(discord.channel_messages), len(discord.dms))

        # 4. 새 글: 최근 글 몇 건을 새 글로 되돌려 게시·알림 확인
        stored = stack.scan("ItemsTable")
        chosen = pick_recent(stored, KEYWORDS_BOT + KEYWORDS_WEB)
        make_new_again(stack, chosen)
        stats = stack.crawl()
        messages, dms = discord.channel_messages[sent_before[0]:], discord.dms[sent_before[1]:]
        posted_urls = {e["url"] for _, m in messages for e in m["embeds"]}
        report["steps"]["4_new_posts"] = {
            "made_new": len(chosen), "new": stats["new"], "saved": stats["saved"], "quiet": stats["quiet"],
            "channels": stats["channels"], "notify": stats["notify"],
            "posted_per_channel": dict(Counter(name for name, m in messages for _ in m["embeds"])),
            "role_mentions": sum(len(m["allowed_mentions"].get("roles", [])) for _, m in messages),
            "dm_length": [len(m["content"]) for _, m in dms], "dm_text": dms[0][1]["content"] if dms else "",
            "sample_channel_message": messages[0][1] if messages else None,
            "ok": stats["saved"] == len(chosen) and stats["quiet"] == 0 and stats["channels"]["posted"] == len(chosen)
            and stats["channels"]["failed"] == 0 and posted_urls == {it["url"] for it in chosen},
        }

        # 5. 목록 API
        status, res = stack.web("GET", "/items")
        size = len(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        per_category = {c: len(stack.web("GET", "/items", query={"category": c})[1]["items"]) for c in ("univ", "contest", "jobs", "tech")}
        dates = [it["date"] for it in res["items"]]
        report["steps"]["5_items_api"] = {
            "status": status, "items": len(res["items"]), "per_category": per_category, "response_kb": round(size / 1024, 1),
            "ok": status == 200 and len(res["items"]) == len(stack.scan("ItemsTable")) == sum(per_category.values())
            and dates == sorted(dates, reverse=True) and size < 6 * 1024 * 1024,   # Lambda 응답 한도 6MB
        }
        report["discord_violations"] = discord.violations
        report["ok"] = all(step["ok"] for step in report["steps"].values()) and not discord.violations

    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
