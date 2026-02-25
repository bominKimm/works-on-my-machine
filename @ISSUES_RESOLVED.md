# JSON Output Refactoring - API Response 직접 반환

## 문제
- Agent가 JSON **파일**을 생성하고 Wrapper가 파일을 읽어서 API response로 변환
- 불필요한 파일 I/O 작업
- 사용자 요구: Agent가 생성한 JSON을 API response로 **직접** 반환

## 해결방법
1. **Agent 프롬프트 수정**: JSON을 stdout 또는 응답으로 직접 출력
2. **Wrapper 수정**: Agent의 응답에서 JSON 추출하여 파싱

## 구현 변경사항

### 1. Agent 프롬프트 수정 (`agents/new_agent_with_tools.py`)
**Phase 3 변경**:
```python
## Phase 3: JSON Response (CRITICAL - API depends on this!)
9. **MANDATORY - Your FINAL RESPONSE must be ONLY a JSON object**:
   - Do NOT include any text before or after the JSON
   - Do NOT wrap it in markdown code blocks
   - Just output the raw JSON object
   - Format: {"vulnerabilities": [...], "attack_scenarios": [...]}
```

**이유**: Agent가 최종 응답을 JSON으로 반환하도록 명시

### 2. Wrapper V2 생성 (`agents/new_agent_wrapper_v2.py`)
**주요 변경**:
- Agent의 `run()` 메서드가 반환한 **문자열**에서 JSON 추출
- 3가지 패턴 지원:
  1. Markdown 코드 블록: ` ```json ... ``` `
  2. JSON 객체 패턴: `{ ... "vulnerabilities" ... }`
  3. 전체 응답이 JSON인 경우

**코드**:
```python
# 응답에서 JSON 객체 추출
json_match = re.search(r'```json\s*\n(.*?)\n```', agent_response, re.DOTALL)
if json_match:
    json_str = json_match.group(1).strip()
else:
    # 마지막 { ... } 블록 찾기
    json_match = re.search(r'(\{[\s\S]*"vulnerabilities"[\s\S]*\})\s*$', agent_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
```

### 3. API 통합 (`api/routers/analyze.py`)
```python
from agents.new_agent_wrapper_v2 import analyze_bicep  # V2 사용
```

## 장점
1. ✅ **파일 I/O 제거**: 더 이상 `security_analysis.json` 파일 생성/읽기 불필요
2. ✅ **간결한 흐름**: Agent 응답 → JSON 파싱 → API response
3. ✅ **유연성**: Markdown 코드 블록, 순수 JSON 등 다양한 형식 지원
4. ✅ **Fallback 유지**: JSON 파싱 실패 시 Markdown fallback

## 테스트 계획
1. Agent가 JSON을 올바른 형식으로 반환하는지 확인
2. Wrapper가 JSON을 정확히 추출/파싱하는지 검증
3. API endpoint에서 structured response 반환 확인

## 다음 단계
- API 테스트 실행
- Agent JSON 응답 형식 검증
- 필요시 Agent 프롬프트 미세 조정

---

# Frontend 렌더링 문제 해결

## 문제
Frontend에서 `/analyze` API 호출 후 응답을 받았지만 결과가 렌더링되지 않음

## 원인 분석

### 1. 파일 형식 검증 문제
- API가 `.bicep` 파일 형식을 허용하지 않음
- `ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}` (bicep 누락)

### 2. File Processor 미지원
- `api/common/mock_services/file_processor.py`가 `.bicep` 파일 처리 로직 없음
- Bicep 파일 업로드 시 에러 발생

### 3. Agent 프롬프트 f-string 충돌
- 프롬프트 내 `{output_path}`, `{"vulnerabilities": [...]}` 등이 Python f-string과 충돌
- `Invalid format specifier` 에러 발생

### 4. Wrapper가 AgentResponse 객체 처리 못함
- Agent의 `run()` 메서드가 `AgentResponse` 객체 반환
- Wrapper가 문자열로 처리하려다 `object of type 'AgentResponse' has no len()` 에러

### 5. Pydantic Validation 에러
- Agent가 `prerequisites`를 리스트로 생성: `['item1', 'item2']`
- API 모델은 문자열 기대: `"item1; item2"`
- `Input should be a valid string [type=string_type, input_value=[...], input_type=list]`

## 해결 방법

### 1. Bicep 파일 형식 허용 (`api/routers/analyze.py`)
```python
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bicep"}  # Bicep 추가
```

### 2. Bicep 파일 처리 로직 추가 (`api/common/mock_services/file_processor.py`)
```python
allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".bicep"}

# Bicep 파일인 경우 그대로 반환
if ext == ".bicep":
    await asyncio.sleep(0.1)
    return file_content.decode('utf-8')
```

### 3. Agent 프롬프트 f-string 충돌 수정 (`agents/new_agent_with_tools.py`)
```python
# Before
- `docker-compose -f {output_path} ps`
- Format: {"vulnerabilities": [...]}

# After
- `docker-compose -f OUTPUT_FILE ps`
- Format: {{"vulnerabilities": [...}}}  # 중괄호 이스케이프
```

### 4. AgentResponse 객체 처리 (`agents/new_agent_wrapper_v2.py`)
```python
agent_response = await convert_func(str(bicep_file), str(compose_file))

# AgentResponse 객체를 문자열로 변환
if hasattr(agent_response, 'message'):
    agent_response_text = agent_response.message
elif hasattr(agent_response, 'content'):
    agent_response_text = agent_response.content
else:
    agent_response_text = str(agent_response)
```

### 5. Prerequisites 자동 변환 (`agents/new_agent_wrapper_v2.py`)
```python
# prerequisites가 리스트인 경우 문자열로 변환
prerequisites = a.get("prerequisites", "None")
if isinstance(prerequisites, list):
    prerequisites = "; ".join(prerequisites)
```

## 테스트 결과

```bash
✅ Status: success
📊 Vulnerabilities: 10
⚡ Attack scenarios: 10

🔴 Sample Vulnerability:
   - ID: VULN-001
   - Title: Hardcoded Weak Credentials
   - Severity: CRITICAL

⚡ Sample Attack:
   - ID: ATTACK-001
   - Name: Credential Theft and Storage Takeover
   - Prerequisites: Network access to port 9000/9001; Knowledge of exposed environment variables
```

## 수정된 파일
1. `api/routers/analyze.py` - Bicep 파일 형식 허용
2. `api/common/mock_services/file_processor.py` - Bicep 파일 처리 로직
3. `agents/new_agent_with_tools.py` - f-string 충돌 수정
4. `agents/new_agent_wrapper_v2.py` - AgentResponse 처리 + prerequisites 변환

## 결과
✅ API가 정상적으로 취약점 및 공격 시나리오 반환
✅ Frontend에서 데이터 렌더링 가능한 형식으로 응답
✅ Pydantic validation 통과

---

# Agent 리포트 형식 통일 및 한국어 작성 명시

## 변경 사항

### 1. 두 Agent의 리포트 형식 통일
- `new_agent.py` (Zero-Tools Agent)
- `new_agent_with_tools.py` (With-Tools Agent)

### 2. 한국어 작성 명시적 지시
**이전:**
```
### 2. Markdown Report (write in Korean; for humans)
```

**이후:**
```
### 2. Markdown Report (MUST write in Korean; for humans)
**필수 포함 내용 (반드시 한국어로 작성):**
**중요**: Markdown 리포트는 반드시 한국어로 작성해야 합니다!
```

### 3. 표준화된 리포트 구조 제공

```markdown
# Red Team 보안 분석 리포트

## 📊 요약
- 배포된 컨테이너: X개
- 발견된 취약점: Y개 (Critical: A, High: B, Medium: C, Low: D)
- 공격 시나리오: Z개

## 🚀 Phase 1: 배포 결과
[컨테이너 목록 및 포트 정보]

## 🔴 Phase 2: Red Team 공격 결과
[수행된 공격 및 발견사항]

## 🔍 발견된 취약점
### VULN-001: [제목] (Critical/High/Medium/Low)
- **영향받는 리소스**: [리소스명]
- **설명**: [상세 설명]
- **증거**: [실제 테스트 결과]
- **개선방안**: [구체적 조치사항]

## ⚡ 공격 시나리오
### ATTACK-001: [공격명] (MITRE: T1XXX)
- **전제조건**: [필요한 접근 권한]
- **공격 단계**:
  1. [단계 1]
  2. [단계 2]
- **예상 영향**: [공격 성공 시 영향]
- **탐지 난이도**: Easy/Medium/Hard
- **발생 가능성**: High/Medium/Low

## 💡 개선 권장사항
1. **긴급 (Critical)**: [조치사항]
2. **높음 (High)**: [조치사항]
3. **중간 (Medium)**: [조치사항]

## 📝 컨테이너 관리
- 상태 확인: `docker-compose -f [파일] ps`
- 중지: `docker-compose -f [파일] down`
- 로그 확인: `docker-compose -f [파일] logs [서비스명]`
```

## 통일된 출력 형식

### JSON Output (API 통합용)
- 영어로 작성 (API 호환성)
- 표준화된 필드명
- Pydantic 스키마 준수

### Markdown Report (사람이 읽을 용도)
- **한국어로 작성** (명시적 지시)
- 동일한 구조 사용
- 이모지로 섹션 구분
- 우선순위별 개선방안 제시

## 수정된 파일
1. `agents/new_agent.py` - Zero-Tools Agent instruction 업데이트
2. `agents/new_agent_with_tools.py` - With-Tools Agent instruction 업데이트

## 기대 효과
✅ 두 Agent 모드 간 일관된 리포트 형식
✅ 한국어 리포트 작성 보장
✅ 사람이 읽기 쉬운 구조화된 리포트
✅ API와 Human-readable 출력 명확히 분리

---

# 보고서 형식 개선: 설계 단계 보안 분석 도구로 재정의

## 핵심 변경사항

### 도구의 목적 재정의
**이전**: Red Team 침투 테스트 도구
**이후**: 설계 단계 보안 위험 분석 및 검증 우선순위 도구

### 보고서 컨셉 변경

| 항목 | 이전 (침투 테스트) | 이후 (설계 분석) |
|------|-----------------|---------------|
| 목적 | 실제 공격 수행 및 침투 | 설계상 위험 식별 및 조기 개선 |
| 초점 | 발견된 취약점 | 공격 가능성 평가 |
| 출력 | 공격 결과 리포트 | 보안 아키텍처 분석 보고서 |
| 대상 | 보안 담당자 | 아키텍트 + 개발자 + 보안 담당자 |
| 시점 | 배포 후 | 배포 전/설계 단계 |

## 새로운 보고서 구조

### 1. Executive Summary
- 즉시 조치 필요 항목 (Critical)
- 핵심 권장사항 Top 3
- 전체 위험 통계

### 2. 아키텍처 분석 결과
- 배포된 리소스 목록
- 네트워크 구성
- 서비스 간 관계

### 3. 보안 위험 평가 (RISK-XXX)
**이전**: VULN-001: 취약점 발견
**이후**: RISK-001: 설계상 보안 위험

**포함 내용**:
- 위험 설명 (설계상 문제점)
- 공격 가능성 (악용 방법)
- 비즈니스 영향 (예상 피해)
- 설계 개선방안:
  - 즉시: 배포 전 필수 조치
  - 단기: 1주일 내
  - 장기: 아키텍처 재설계
- 관련 기준 (CIS, OWASP, NIST)

### 4. 공격 가능성 시나리오 (SCENARIO-XXX)
**이전**: ATTACK-001: 공격 수행 결과
**이후**: SCENARIO-001: 예상 공격 시나리오

**포함 내용**:
- 공격 개요 및 목표
- 전제 조건
- 예상 공격 흐름 (다이어그램)
- 탐지 가능성 평가
- 실제 공격 사례 참조

### 5. 검증 우선순위 (NEW!)
**Phase 1: 긴급 검증 (P0 - 배포 전 필수)**
- 치명적 위험 제거
- 체크리스트 제공
- 검증 방법 및 예상 소요 시간

**Phase 2: 높은 우선순위 (P1 - 1주일 내)**
- 주요 공격 경로 차단

**Phase 3: 중간 우선순위 (P2 - 1개월 내)**
- 전체 보안 수준 향상

### 6. 설계 단계 개선사항 (NEW!)
**즉시 적용 가능 (배포 전)**:
- 문제되는 설정
- 권장 설정
- 수정된 Bicep 코드 예시

**아키텍처 재설계 고려사항**:
- Zero Trust 아키텍처 적용
- 심층 방어 전략

### 7. 위험 매트릭스 (NEW!)
```
   영향도
   ↑
High│ [HIGH]  │ [CRITICAL] │
Med │ [MED]   │ [HIGH]     │
Low │ [LOW]   │ [MED]      │
    └─────────┴────────────┴→ 발생가능성
```

### 8. 참고자료 (NEW!)
- CIS Benchmarks
- OWASP Top 10
- NIST Cybersecurity Framework
- Azure Security Baseline
- Azure Well-Architected Framework

## 용어 변경

| 이전 | 이후 |
|------|------|
| Red Team 공격 리포트 | 보안 아키텍처 분석 보고서 |
| 취약점 (Vulnerability) | 보안 위험 (Security Risk) |
| 공격 수행 (Attack Executed) | 공격 가능성 분석 (Attack Possibility) |
| 발견된 문제 (Issues Found) | 설계상 위험 (Design Risks) |
| 침투 테스트 결과 | 설계 단계 보안 평가 |

## 가치 제안 변경

**이전**: 
"배포된 시스템을 공격하여 취약점을 찾아냅니다"

**이후**: 
"설계 단계에서 보안 위험을 조기에 발견하고, 배포 전 개선하여 안전한 아키텍처를 구축합니다"

## 사용자 혜택

1. **조기 발견**: 배포 전에 보안 위험 식별
2. **비용 절감**: 배포 후 수정보다 설계 단계 수정이 저렴
3. **명확한 우선순위**: P0/P1/P2로 검증 계획 수립
4. **실행 가능한 가이드**: Bicep 코드 예시 제공
5. **컴플라이언스**: CIS, OWASP 기준 자동 매핑

## 수정된 파일
1. `agents/new_agent.py` - 보고서 템플릿 전면 개편
2. `agents/new_agent_with_tools.py` - 보고서 템플릿 전면 개편

## 결과
✅ 도구의 목적을 명확히 재정의
✅ 설계 단계에 최적화된 보고서 형식
✅ 검증 우선순위 및 실행 계획 제공
✅ 개발자와 아키텍트에게 유용한 정보 제공
✅ 컴플라이언스 및 Best Practice 자동 매핑
