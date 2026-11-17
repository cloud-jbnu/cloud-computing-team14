"""테스트 공통 설정. 네트워크·AWS 없이 돌아야 합니다.

실행: crawler 폴더에서 `pytest`
"""
import sys
from pathlib import Path

import pytest

# Lambda에서는 src/가 최상위이므로 테스트에서도 `import handler`, `from common import http`로 불러옵니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixture_text():
    """tests/fixtures/ 에 저장해 둔 HTML·JSON 조각을 문자열로 읽습니다."""
    def read(name):
        return (FIXTURES / name).read_text(encoding="utf-8")
    return read
