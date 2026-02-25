# SecurityBlueprint Agent

시스템 아키텍처 다이어그램을 업로드하면 BiCep 코드로 변환하고, 보안 취약점을 자동 분석하는 서비스입니다.

## 주요 기능

- **아키텍처 파일 업로드** - PDF, PNG, JPG 형식의 아키텍처 다이어그램 지원
- **BiCep 변환** - 아키텍처 다이어그램을 Azure BiCep 코드로 변환
- **Policy 검증** - Azure Policy 준수 여부 검증 (NSG, 네트워크 규칙, HTTPS 등)
- **RedTeam 분석** - 보안 취약점 탐지, 공격 시뮬레이션, MITRE ATT&CK 매핑
- **보고서 생성** - 심각도별 취약점 목록 및 보안 개선 권장사항

## 기술 스택

| 구분     | 기술                           |
| -------- | ------------------------------ |
| Frontend | React.js (개발 예정)<br/>Streamlit (로컬 데모용 임시 구현) |
| Backend  | FastAPI + Gunicorn + Uvicorn   |
| LLM      | GitHub Copilot SDK, OpenAI SDK |
| Language | Python 3.10+                   |

## 빠른 시작

```bash
# 환경 설정 및 의존성 설치
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 서버 실행
uvicorn api.main:app --reload --port 8000        # 터미널 1 (API)
streamlit run streamlit_app/app.py --server.port 8501  # 터미널 2 (UI - 데모용)
```

브라우저에서 `http://localhost:8501` 접속 후 아키텍처 파일을 업로드하면 분석이 시작됩니다.

> **Note:** 현재 Streamlit UI는 로컬 데모용 임시 구현입니다. 프로덕션 환경에서는 `frontend/` 디렉토리의 React.js 기반 UI를 사용할 예정입니다.

> 상세한 환경 설정 및 실행 방법은 [DEVELOPMENT.md](docs/DEVELOPMENT.md)를 참조하세요.

## 프로젝트 구조

```text
/
├── api/                     # FastAPI 백엔드
│   ├── main.py
│   ├── models/              # Pydantic 요청/응답 모델
│   └── routers/             # API 엔드포인트
│       ├── health.py        #   GET  /api/v1/health
│       ├── analyze.py       #   POST /api/v1/analyze
│       └── copilot.py       #   POST /copilot
├── agents/                  # 분석 에이전트
│   ├── agent.py             #   🆕 Local Attack Agent (실제 침투 테스트 수행)
│   ├── mock_agents.py       #   Policy Agent (Mock)
│   └── prompts.py           #   LLM 프롬프트 템플릿
├── mock_services/           # Mock 서비스 (추후 실제 구현 전환)
│   ├── file_processor.py    #   파일 전처리
│   ├── bicep_transformer.py #   BiCep 변환
│   └── blob_storage.py      #   Azure Blob Storage
├── frontend/                # React.js UI (개발 예정)
│   └── (React 프로젝트)
├── streamlit_app/           # Streamlit UI (로컬 데모용 임시 구현)
│   └── app.py
├── samples/                 # 샘플 BiCep 코드
├── tests/                   # 테스트
├── docs/                    # 문서
├── requirements.txt
└── gunicorn.conf.py

## 🆕 Local Attack Agent (RedTeam Agent)

Bicep 코드를 분석하여 로컬 환경(Docker)에서 실제로 구현하고 자동 공격을 수행하는 Agent입니다.

### 주요 기능
- **Bicep 파싱**: Azure 리소스 자동 추출 (VM, SQL, Storage 등)
- **Docker 배포**: 로컬 컨테이너 환경 자동 구축
- **Agent Loop**: GitHub Copilot SDK 기반 동적 공격 전략 (LLM이 도구 선택)
- **자동 공격**: Nmap, Hydra, SQLMap, Metasploit 실행
- **동적 보고서**: LLM 기반 한국어 침투 테스트 보고서 생성

### 아키텍처
```
Bicep 코드
    ↓
[Phase 1] 파싱 및 배포
    ↓ BicepParser → ResourceMapper → DockerComposer
로컬 Docker 환경
    ↓
[Phase 2] Agent Loop (LLM 기반 동적 공격)
    ├─ LLM이 환경 분석
    ├─ 공격 도구 선택 (Tool Calling)
    ├─ 도구 실행 (Nmap/Hydra/SQLMap/Metasploit)
    ├─ 결과 관찰
    └─ 재계획 (최대 15회 반복)
    ↓
[Phase 3] 결과 분석 및 보고서 생성
    └─ LLM 기반 한국어 보고서
```

### 빠른 시작
```bash
# Agent 실행
python agents/agent.py samples/sample_bicep.bicep

# 결과: 12개 리소스 파싱 → Docker 배포 → Agent Loop 공격 → 보고서 생성
```

### API에서 사용
```python
from agents.agent import LocalAttackAgent

agent = LocalAttackAgent()
result = await agent.analyze(bicep_code)  # AnalysisResult 반환
```

### 주의사항
- **Docker 필수**: Docker가 실행 중이어야 합니다
- **실행 시간**: 5-15분 소요 (배포 + 공격)
- **의존성**: GitHub Copilot SDK, 공격 도구 (Nmap, Hydra, SQLMap, Metasploit)
- **메모리**: 최소 4GB, 권장 8GB (SQL Server 포함 시)

📖 **상세 가이드**: [docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md)

---
```

## API 엔드포인트

| Method | Path             | 설명                      |
| ------ | ---------------- | ------------------------- |
| GET    | `/api/v1/health` | 헬스 체크                 |
| POST   | `/api/v1/analyze`| 아키텍처 파일 분석        |
| POST   | `/copilot`       | GitHub Copilot SDK 테스트 |

API 문서는 서버 실행 후 `http://localhost:8000/docs`에서 확인할 수 있습니다.

## 문서

| 문서 | 설명 |
| ---- | ---- |
| [API.md](docs/API.md) | RESTful API 명세, 엔드포인트 상세, 요청/응답 예시 |
| [AGENT_GUIDE.md](docs/AGENT_GUIDE.md) | 🆕 Local Attack Agent 사용 가이드, 설치, 예제 |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | 개발 환경 설정, 컴포넌트별 실행, 테스트, 실제 구현 전환 가이드 |
| [DESIGN.md](docs/DESIGN.md) | 아키텍처 설계, 파이프라인 흐름, 컴포넌트 명세 |
| [WORKFLOW.md](docs/WORKFLOW.md) | 에이전트 워크플로우 분석, 코드 흐름 상세, 전환 계획 |
| [FRONTEND.md](docs/FRONTEND.md) | React.js 프론트엔드 기술 스택 및 구현 가이드 (예정) |
