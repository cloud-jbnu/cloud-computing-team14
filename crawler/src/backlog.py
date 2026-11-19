"""처음 수집하는 사이트의 밀린 글은 저장만 하고 디스코드에 알리지 않습니다.

처음 배포하거나 새 사이트를 붙이면 그 사이트 목록에 있던 글(점핏 58건 등)이 한꺼번에 새 글로 잡힙니다.
게시일이 없는 사이트는 몇 주 된 글도 수집한 날짜가 되므로, 그대로 두면 채널 게시와 키워드 DM이 쏟아집니다.

사이트를 처음 본 실행에서 그때의 새 글 id를 SEEN_TABLE에 "밀린 글"로 적어 둡니다 (키 source#사이트, 만료 없음).
밀린 글은 한 번에 처리하는 상한 때문에 몇 번의 실행에 나눠 저장되더라도 게시·알림에서 빠지고,
요약과 저장은 평소대로 합니다. 그 뒤에 올라온 글은 평소처럼 알립니다.
"""
import time

import dedupe

KEY = "source#{site}"


def quiet_ids(seen_table, items, now=None):
    """items 중 게시·알림하지 않을 글의 id 집합.

    처음 보는 사이트는 지금 잡힌 새 글을 밀린 글로 적고 모두 조용히 둡니다.
    상한으로 미룬 글까지 적어야 하므로 cap()보다 먼저 부릅니다.
    """
    ids_by_site = {}
    for item in items:
        ids_by_site.setdefault(dedupe.site_of(item), set()).add(item["id"])
    if not ids_by_site:
        return set()

    keys = [KEY.format(site=site) for site in ids_by_site]
    rows = dedupe.batch_get(seen_table, "seenKey", keys, ["seenKey", "backlogIds"])
    backlog = {row["seenKey"]: set(row.get("backlogIds") or ()) for row in rows}

    errors = seen_table.meta.client.exceptions
    quiet = set()
    for site, ids in ids_by_site.items():
        key = KEY.format(site=site)
        if key in backlog:
            quiet |= ids & backlog[key]
            continue
        try:
            seen_table.put_item(
                Item={"seenKey": key, "site": site, "backlogIds": ids, "startedAt": int(now if now is not None else time.time())},
                ConditionExpression="attribute_not_exists(seenKey)",   # 동시에 돈 다른 실행이 먼저 적었으면 그대로 둠
            )
        except errors.ConditionalCheckFailedException:
            pass
        quiet |= ids
        print(f"[{site}] 처음 수집하는 사이트: 지금 있는 글 {len(ids)}건은 저장만 하고 알리지 않음")
    return quiet
