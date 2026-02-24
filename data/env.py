"""
.env 파일 로드 (OpenAI / Azure OpenAI 키 등).

python-dotenv로 프로젝트 루트 및 cwd의 .env를 os.environ에 로드.
패키지: pip install python-dotenv (실행할 Python과 동일한 환경에 설치할 것)
"""

from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    import sys
    print(
        "오류: python-dotenv가 설치되지 않았습니다.\n"
        "  pip install python-dotenv\n"
        "conda/venv 사용 시, 스크립트를 실행하는 Python과 같은 환경에 설치해야 합니다.\n"
        "예: conda 활성화 후 `python data/generate_dummy_data.py` (전체 경로 python3.11 대신)",
        file=sys.stderr,
    )
    sys.exit(1)

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")
load_dotenv(Path.cwd() / ".env")
