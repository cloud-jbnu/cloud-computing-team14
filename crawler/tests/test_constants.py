"""category·fields 목록이 여러 곳에서 어긋나지 않았는지 확인합니다.

크롤러 안에서는 common/item.py의 목록 하나만 씁니다. 웹·API·문서는 따로 배포되거나 다른 언어라
같은 목록을 복사해 두었으므로, 한쪽만 고치면 여기서 실패합니다.
"""
import re
from pathlib import Path

import channels
import notify
import summarize
from common.item import CATEGORIES, FIELDS
from sources import dev_event, jumpit

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def web_ids(name):
    """web/js/data.js의 window.<name> = [{ id: '...' }, ...] 에서 id만 순서대로."""
    block = re.search(rf"window\.{name}\s*=\s*\[(.*?)\];", read("web/js/data.js"), re.S)
    return re.findall(r"id:\s*'(\w+)'", block[1])


def doc_values(column):
    """docs/api.md Item 표에서 | `column` | ... | 줄의 값 목록."""
    line = next(l for l in read("docs/api.md").splitlines() if l.startswith(f"| `{column}` |"))
    return re.findall(r"`(\w+)`", line)[1:]


def test_web_uses_same_lists():
    assert web_ids("CATEGORIES") == CATEGORIES
    assert web_ids("FIELDS") == FIELDS


def test_docs_use_same_lists():
    assert doc_values("category") == CATEGORIES
    assert doc_values("fields") == FIELDS


def test_api_accepts_same_categories():
    # CATEGORIES = ("univ", ...) 상수(fix/api-items-latest 이후) 또는 예전의 category not in {...} 줄
    source = read("api/src/items.py")
    allowed = re.search(r"^CATEGORIES\s*=\s*\(([^)]*)\)", source, re.M) or re.search(r"category not in \{([^}]*)\}", source)
    assert sorted(re.findall(r'"(\w+)"', allowed[1])) == sorted(CATEGORIES)


def test_category_settings_cover_every_category():
    assert set(notify.CATEGORY_LABEL) == set(CATEGORIES)
    assert set(channels.CATEGORY_COLOR) == set(CATEGORIES)
    assert set(channels.CATEGORY_CHANNEL) | {"univ"} == set(CATEGORIES)   # 학교 글은 학교 이름 채널로 감


def test_source_tags_map_to_known_fields():
    assert set(dev_event.FIELD_TAGS.values()) <= set(FIELDS)
    assert {field for _, field in jumpit.FIELD_KEYWORDS} <= set(FIELDS)


def test_prompt_defines_every_field():
    for field in FIELDS:
        assert f"{field}:" in summarize.SYSTEM_PROMPT, f"프롬프트에 {field} 기준이 없음"
