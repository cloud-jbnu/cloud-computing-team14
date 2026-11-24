"""통합 테스트 공통 설정. 네트워크·AWS 계정 없이 돕니다 (moto가 DynamoDB를 흉내 냄).

실행: 저장소 맨 위에서 `pip install -r tests/integration/requirements.txt` → `pytest tests/integration`
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
