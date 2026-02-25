# 개발 가이드

## 사전 요구사항

- Python 3.10+
- pip

## 초기 설정

```bash
# 가상 환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 값 입력
```

## 컴포넌트별 실행

### API 서버

```bash
# 개발 모드 (자동 리로드)
uvicorn api.main:app --reload --port 8000

# 프로덕션 모드
gunicorn -c gunicorn.conf.py api.main:app
```

API 엔드포인트 테스트:

```bash
# 헬스 체크
curl http://localhost:8000/api/v1/health

# 파일 분석
echo "test" > /tmp/test.png
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@/tmp/test.png"

# Swagger UI → http://localhost:8000/docs
```

### Streamlit UI (로컬 데모용)

> **Note:** Streamlit UI는 로컬 데모 및 개발 테스트 목적의 임시 구현입니다. 프로덕션 환경에서는 `frontend/` 디렉토리의 React.js 기반 UI를 사용할 예정입니다.

API 서버가 먼저 실행 중이어야 합니다.

```bash
streamlit run streamlit_app/app.py --server.port 8501
```

기능:

- 사이드바에서 아키텍처 다이어그램 업로드 (PDF/PNG/JPG)
- 5단계 파이프라인 진행 상태 표시
- 취약점 목록 (심각도 필터링)
- 공격 시뮬레이션 시나리오
- Policy 검증 결과
- 마크다운 보고서 렌더링 및 다운로드

### React.js UI (프로덕션용, 개발 예정)

`frontend/` 디렉토리에 별도 React.js 프로젝트로 구현될 예정입니다. 기존 FastAPI 엔드포인트를 사용하며, 상세 기술 스택 및 개발 가이드는 [FRONTEND.md](FRONTEND.md) 참조 (예정).

### Mock 서비스 단독 테스트

```bash
python3 -c "
import asyncio
from mock_services import mock_file_preprocessing, mock_bicep_transform
from agents import mock_policy_agent

async def main():
    bicep = await mock_file_preprocessing(b'dummy', 'test.pdf')
    print(f'BiCep 코드 길이: {len(bicep)} bytes')

    bicep2 = await mock_bicep_transform(b'dummy', 'test.png')
    print(f'변환된 BiCep 길이: {len(bicep2)} bytes')

    result = await mock_policy_agent(bicep)
    print(f'Policy 검증: {result[\"status\"]}')
    print(f'  위반: {len(result[\"violations\"])}개')
    print(f'  권장: {len(result[\"recommendations\"])}개')

asyncio.run(main())
"
```

### RedTeam Agent 단독 테스트

현재 Mock 구현 (정적 규칙 기반). 추후 Semantic Kernel + GitHub Copilot SDK로 교체 예정.

```bash
python3 -c "
import asyncio
from pathlib import Path
from agents import RedTeamAgent

async def main():
    bicep = Path('samples/sample_bicep.bicep').read_text()
    agent = RedTeamAgent()
    result = await agent.analyze(bicep)

    print(f'취약점: {len(result.vulnerabilities)}개')
    for sev, cnt in result.vulnerability_count.items():
        if cnt > 0:
            print(f'  {sev}: {cnt}개')
    print(f'공격 시나리오: {len(result.attack_scenarios)}개')
    print()
    print(result.report)

asyncio.run(main())
"
```

## 테스트

```bash
# 전체 테스트 실행
pytest tests/ -v

# 특정 테스트 파일 실행
pytest tests/test_api.py -v

# 커버리지 리포트
pytest tests/ --cov=api --cov=agents --cov=api/common/mock_services --cov-report=html
```

---

## 코드 스타일

```bash
# 린팅
ruff check .

# 포매팅
ruff format .

# 타입 체크
mypy api/ agents/ api/common/mock_services/
```

---

## 트러블슈팅

| 문제 | 해결 |
| ---- | ---- |
| `ModuleNotFoundError: No module named 'xxx'` | 가상 환경 활성화 확인: `source .venv/bin/activate` |
| API 서버 포트 충돌 | `lsof -i :8000` 후 프로세스 종료, 또는 다른 포트 사용 |
| Streamlit 연결 실패 | API 서버가 먼저 실행 중인지 확인 |
| `.env` 파일 인식 안됨 | `.env.example`을 복사하여 `.env` 생성 확인 |

--- 개발 진행 상태

| Phase | 내용                     | 상태 |
| ----- | ------------------------ | ---- |
| 1     | 기반 구조 및 Mock 서비스 | 완료 |
| 2     | RedTeam Agent (Mock)     | 완료 |
| 3     | FastAPI 구현             | 완료 |
| 4     | Streamlit UI 구현        | 완료 |
| 5     | 통합 및 테스트           | 완료 |

## 실제 구현 전환 가이드

### RedTeam Agent → Semantic Kernel + GitHub Copilot SDK

```bash
pip install semantic-kernel openai github-copilot-sdk
```

환경 변수 설정 (택 1):

```bash
# GitHub Models (GitHub Copilot SDK)
export GITHUB_TOKEN="ghp_..."
export GITHUB_MODEL_ID="gpt-4o"

# Azure OpenAI
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://{resource}.openai.azure.com/"

# OpenAI
export OPENAI_API_KEY="sk-..."
```
