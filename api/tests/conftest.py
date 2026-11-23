"""API Lambda 테스트 공통 설정. 네트워크·AWS 없이 돌아야 합니다.

실행: api 폴더에서 `pytest` (패키지는 crawler/requirements.txt와 같음: boto3, pytest)
"""
import sys
from pathlib import Path

# Lambda에서는 src/가 최상위이므로 테스트에서도 `import chat`으로 불러옵니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
