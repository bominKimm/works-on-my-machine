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
| Frontend | Streamlit                      |
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
streamlit run streamlit_app/app.py --server.port 8501  # 터미널 2 (UI)
```

브라우저에서 `http://localhost:8501` 접속 후 아키텍처 파일을 업로드하면 분석이 시작됩니다.

> 상세한 환경 설정 및 실행 방법은 [DEVELOPMENT.md](DEVELOPMENT.md)를 참조하세요.

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
│   ├── redteam_agent.py     #   RedTeam 보안 분석
│   ├── mock_agents.py       #   Policy Agent (Mock)
│   └── prompts.py           #   LLM 프롬프트 템플릿
├── mock_services/           # Mock 서비스 (추후 실제 구현 전환)
│   ├── file_processor.py    #   파일 전처리
│   ├── bicep_transformer.py #   BiCep 변환
│   └── blob_storage.py      #   Azure Blob Storage
├── streamlit_app/           # Streamlit UI
│   └── app.py
├── samples/                 # 샘플 BiCep 코드
├── tests/                   # 테스트
├── requirements.txt
└── gunicorn.conf.py
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
| [DEVELOPMENT.md](DEVELOPMENT.md) | 개발 환경 설정, 컴포넌트별 실행, 테스트, 실제 구현 전환 가이드 |
| [DESIGN.md](DESIGN.md) | 아키텍처 설계, 파이프라인 흐름, 컴포넌트 명세 |
| [WORKFLOW.md](WORKFLOW.md) | 에이전트 워크플로우 분석, 코드 흐름 상세, 전환 계획 |
