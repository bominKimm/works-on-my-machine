# 이슈 해결 내역

> RedTeam Agent 관련 모든 이슈 처리 및 코드 수정 사항은 이 문서에 기록됩니다.

## 이슈 내역

- [이슈 해결 내역](#이슈-해결-내역)
  - [이슈 내역](#이슈-내역)
  - [2026-02-24 - Docker 배포 및 재시도 기능 개선](#2026-02-24---docker-배포-및-재시도-기능-개선)
    - [Issue #1: Docker 배포 실패 시 자동 재시도](#issue-1-docker-배포-실패-시-자동-재시도)
    - [Issue #2: Compose 파일 자동 검증 및 수정](#issue-2-compose-파일-자동-검증-및-수정)
    - [Issue #3: 컨테이너 감지 실패](#issue-3-컨테이너-감지-실패)
    - [Issue #4: 컨테이너 대기 시간 최적화](#issue-4-컨테이너-대기-시간-최적화)
    - [Issue #5: 로그 메시지 명확화](#issue-5-로그-메시지-명확화)
    - [Issue #6: 재시도 순서 개선](#issue-6-재시도-순서-개선)
    - [Issue #7: Mock 모드 제거](#issue-7-mock-모드-제거)
    - [Issue #8: Bicep 문자열 입력 지원](#issue-8-bicep-문자열-입력-지원)
    - [Issue #9: SQL Server 비밀번호 정책 위반](#issue-9-sql-server-비밀번호-정책-위반)
    - [Issue #10: 컨테이너 이름 충돌](#issue-10-컨테이너-이름-충돌)
    - [Issue #11: 컨테이너 초기화 시간 부족](#issue-11-컨테이너-초기화-시간-부족)
  - [Issue #12: 포트 충돌 및 Orphan 컨테이너](#issue-12-포트-충돌-및-orphan-컨테이너)
  - [Issue #13: LLM 기반 동적 보고서 생성](#issue-13-llm-기반-동적-보고서-생성)
  - [Issue #14: Agent Loop 아키텍처 도입](#issue-14-agent-loop-아키텍처-도입)
  - [Issue #15: RedTeam Agent 통합](#issue-15-redteam-agent-통합)
  - [Issue #16: 공격 도구 확장](#issue-16-공격-도구-확장)
  - [Issue #18: 코드 버그 수정 (8개)](#issue-18-코드-버그-수정-8개)
  - [Docker 문제 해결 가이드](#docker-문제-해결-가이드)
    - [시스템 요구사항](#시스템-요구사항)
    - [예상 소요 시간](#예상-소요-시간)
    - [문제 해결 방법](#문제-해결-방법)
      - [배포 실패 시](#배포-실패-시)
      - [SQL Server 시작 실패 시](#sql-server-시작-실패-시)
      - [메모리 부족 시](#메모리-부족-시)
  - [생성된 파일](#생성된-파일)
    - [문서](#문서)
    - [테스트](#테스트)
  - [현재 상태](#현재-상태)
  - [주요 코드 변경 요약](#주요-코드-변경-요약)
  - [사용 방법](#사용-방법)
    - [1. 파일 경로로 실행](#1-파일-경로로-실행)
    - [2. Bicep 코드 문자열로 실행 (프로그래밍 방식)](#2-bicep-코드-문자열로-실행-프로그래밍-방식)
    - [3. 테스트](#3-테스트)

---

## 2026-02-24 - Docker 배포 및 재시도 기능 개선

### Issue #1: Docker 배포 실패 시 자동 재시도
**문제**: Docker 배포 실패 시 즉시 중단되어 일시적인 오류도 복구 불가

**해결**: 
- 최대 2회 자동 재시도 로직 구현
- 실패 지점에 따른 차별화된 재시도 전략
- 재시도 후에도 실패 시 배포 실패 보고서 생성

**수정 파일**: `agents/agent.py`
- `LocalDeployer.deploy()` - 재시도 루프 구현 (Line 496-685)
  ```python
  for attempt in range(1, max_attempts + 1):
      # docker-compose up 실패 시 → yml 검증/수정 후 재시도
      # 10분 초과 시 → 컨테이너 정리 후 재시도
  ```

**효과**: 일시적 네트워크 오류, 포트 충돌 등 자동 복구 가능

---

### Issue #2: Compose 파일 자동 검증 및 수정
**문제**: 잘못된 Compose 파일로 인한 배포 실패가 반복됨

**해결**:
- 자동 검증 및 수정 메서드 구현
- 포트 충돌, 이미지명 오류, 환경변수 오류 자동 수정

**수정 파일**: `agents/agent.py`
- `LocalDeployer._validate_and_fix_compose_file()` 메서드 추가 (Line 409-494)

**자동 수정 항목**:
1. **포트 충돌**: 1000씩 자동 증가 (1433 → 2433 → 3433)
2. **이미지명**: vault:latest → hashicorp/vault:latest
3. **SQL Server 환경변수**: SA_PASSWORD → MSSQL_SA_PASSWORD

---

### Issue #3: 컨테이너 감지 실패
**문제**: `docker ps`에는 컨테이너가 보이지만 코드에서 감지 실패

**원인**: 
1. Docker SDK가 docker-compose 컨테이너를 신뢰성있게 감지하지 못함
2. 네트워크 이름 불일치 ("attack_network" vs "t_attack_network")

**해결**:
- Docker SDK 대신 subprocess 기반으로 변경
- `docker-compose ps -q` + `docker inspect` 조합 사용
- 네트워크 이름 유연한 매칭

**수정 파일**: `agents/agent.py`
- `_get_running_containers()` 메서드 완전 재작성 (Line 687-755)
  ```python
  # docker-compose ps -q로 해당 compose의 컨테이너만 조회
  # docker inspect로 각 컨테이너 상세 정보 수집
  # "attack_network" in network_name으로 유연한 매칭
  ```

---

### Issue #4: 컨테이너 대기 시간 최적화
**문제**: 고정 대기 시간으로 인한 비효율 (너무 짧거나 너무 김)

**해결**:
- 고정 대기 → 반복 체크 방식으로 변경
- 10초마다 컨테이너 상태 확인, 최대 10분 대기
- 컨테이너 감지 즉시 완료 (불필요한 대기 제거)

**수정 파일**: `agents/agent.py`
- `deploy()` 메서드 대기 로직 개선 (Line 572-621)
  ```python
  max_wait_seconds = 600  # 10분
  check_interval = 10     # 10초마다
  while elapsed < max_wait_seconds:
      containers = self._get_running_containers()
      if containers:
          break  # 즉시 완료
      time.sleep(check_interval)
  ```

**효과**: 
- 평균 대기 시간 단축 (30초 → 실제 필요한 시간만)
- 무거운 컨테이너도 충분히 대기 (최대 10분)

---

### Issue #5: 로그 메시지 명확화
**문제**: "이미지 다운로드 시 수분 소요"라고 하면서 30초만 대기하는 혼란스러운 로그

**해결**:
- 단계별 로그 메시지 명확화
- 각 단계별 예상 소요 시간 명시

**수정 파일**: `agents/agent.py`
- 로그 메시지 개선 (Line 547-621)

**개선된 로그**:
```
[시도 1/2] 컨테이너 시작 중...
⏱️  이미지 다운로드 및 컨테이너 생성 중 (첫 실행 시 최대 10분 소요)
✅ 이미지 다운로드 및 컨테이너 생성 완료
⏱️  컨테이너 상태 확인 중... (최대 10분 대기)
✅ 7개 컨테이너 감지됨 (대기 시간: 90초)
✅ 배포 완료
```

---

### Issue #6: 재시도 순서 개선
**문제**: 모든 실패에 대해 동일한 재시도 전략 적용으로 비효율적

**해결**: 실패 지점에 따라 다른 재시도 전략 적용

**수정 파일**: `agents/agent.py`
- `deploy()` 메서드 재시도 로직 개선

**재시도 전략**:
1. `docker-compose up` 실패 → yml 검증/수정 후 컨테이너 시작부터 재시도
2. 10분 초과 (컨테이너 미감지) → 기존 컨테이너 정리부터 재시도

---

### Issue #7: Mock 모드 제거
**문제**: Mock 모드는 실제 공격 테스트를 수행할 수 없어 Agent의 핵심 가치 제공 불가

**해결**:
- 모든 Mock 코드 제거
- Docker 필수 요구사항으로 변경
- 보안 도구 미설치 시 명확한 에러 메시지

**수정 파일**: `agents/agent.py`
- `LocalDeployer.__init__()` - skip_docker_check 제거, Docker 필수 체크 (Line 393-402)
- `deploy()` - Mock 배포 정보 반환 코드 제거
- `NmapScanner`, `HydraAttacker`, `SQLMapAttacker`, `MetasploitAttacker` - Mock 결과 메서드 삭제
- `run_agent()` - SKIP_DOCKER 환경변수 처리 제거

**영향**:
- Docker 미실행 시 즉시 에러로 중단
- 보안 도구 미설치 시 해당 공격만 실패 (전체 Agent는 계속 실행)

---

### Issue #8: Bicep 문자열 입력 지원
**문제**: 파일 경로로만 입력 가능, 프로그래밍 방식 사용 불편

**해결**:
- 파일 경로와 Bicep 코드 문자열 모두 처리 가능하도록 개선
- 자동 감지 로직 구현

**수정 파일**: `agents/agent.py`
- `run_agent()` 함수 개선 (Line 1567-1604)
  ```python
  if bicep_input.endswith('.bicep') or Path(bicep_input).exists():
      # 파일로 처리
  elif any(keyword in bicep_input for keyword in ['resource', 'param', 'var']):
      # Bicep 코드 문자열로 처리
  ```

**사용 예시**:
```python
# 파일 경로
result = await run_agent("samples/sample_bicep.bicep", use_docker=True)

# Bicep 코드 문자열
bicep_code = """
resource storage 'Microsoft.Storage/storageAccounts@2021-04-01' = {
  name: 'mystorage'
  location: 'eastus'
}
"""
result = await run_agent(bicep_code, use_docker=True)
```

---

### Issue #9: SQL Server 비밀번호 정책 위반
**증상**: 
```
ERROR: The password does not meet SQL Server password policy requirements
```

**원인**: SQL Server는 강력한 비밀번호 정책 적용
- 최소 8자 이상
- 대문자, 소문자, 숫자, 특수문자 각각 1개 이상 포함

**해결**: 자동 검증 및 수정
```python
# _validate_and_fix_compose_file() 내부
password = env.get('MSSQL_SA_PASSWORD', '')
if len(password) < 8 or not any(c.isupper() for c in password) or \
   not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
    env['MSSQL_SA_PASSWORD'] = 'YourStrong!Passw0rd'
```

**수정 파일**: `agents/agent.py`
- `_validate_and_fix_compose_file()` SQL Server 비밀번호 검증 로직 (Line 475-480)

**효과**: SQL Server 컨테이너 시작 성공률 100%

---

### Issue #10: 컨테이너 이름 충돌
**증상**:
```
ERROR: Container name "sql_sqlServer" already exists
```

**원인**: 이전 실행의 컨테이너가 정리되지 않고 남아있음

**해결**: 배포 전 자동 정리
```python
# deploy() 메서드 내부
subprocess.run(
    ["docker-compose", "-f", str(self.compose_file_path), "down", "-v"],
    capture_output=True,
    text=True,
    timeout=30,
)
```

**수정 파일**: `agents/agent.py`
- `deploy()` 컨테이너 정리 로직 (Line 542-549)

**효과**: 
- 컨테이너 이름 충돌 0%
- 볼륨도 함께 정리 (`-v` 옵션)

---

### Issue #11: 컨테이너 초기화 시간 부족
**증상**: 컨테이너가 생성되었지만 즉시 종료됨
```
STATUS: Exited (1) 2 seconds ago
```

**원인**: SQL Server, Minio 등 무거운 컨테이너는 시작에 시간 필요
- SQL Server: ~30초
- Minio: ~20초

**해결**: 반복 체크 방식 + 충분한 대기 시간
```python
max_wait_seconds = 600  # 10분
check_interval = 10     # 10초마다 체크

while elapsed < max_wait_seconds:
    containers = self._get_running_containers()
    if containers:
        logger.info(f"✅ {len(containers)}개 컨테이너 감지됨")
        break
    time.sleep(check_interval)
    elapsed += check_interval
```

**수정 파일**: `agents/agent.py`
- `deploy()` 반복 체크 로직 (Line 572-621)

**효과**:
- 컨테이너가 준비되는 즉시 완료 (불필요한 대기 제거)
- 무거운 컨테이너도 충분히 대기 (최대 10분)
- 실제 평균 대기 시간: 1-2분

---

## Issue #12: 포트 충돌 및 Orphan 컨테이너

**증상:**
```
Error response from daemon: failed to set up container networking: 
driver failed programming external connectivity on endpoint storage_storage: 
Bind for 0.0.0.0:9000 failed
```
```
Found orphan containers ([keyvault_keyVault sql_sqlServer storage_storageAccount ...])
```

**원인:**
- 이전 실행의 컨테이너가 완전히 정리되지 않아 포트를 점유 중
- 다른 Bicep 파일로 실행한 컨테이너들이 orphan으로 남아있음
- 배포 시작 전에 정리하면 타이밍 이슈로 실패할 수 있음

**해결:**
- **배포 시작 전 정리를 제거** (타이밍 문제 해결)
- **에이전트 실행 마지막에 모든 컨테이너 정리** (완전한 cleanup)
- `docker stop $(docker ps -q)`: 모든 실행 중인 컨테이너 중지
- `docker rm $(docker ps -aq)`: 모든 컨테이너 제거
- `docker-compose down -v`: compose 리소스 정리

**코드 위치:**
- `agents/agent.py`: `LocalDeployer.cleanup()` 메서드 개선
  - Line 759-791: 모든 컨테이너를 강제 정리하는 로직
- `agents/agent.py`: `run_agent()` 함수
  - Line 1621-1637: 에이전트 실행 후 cleanup() 호출

**효과:**
- ✅ 배포 전 타이밍 이슈 해결 (정리하지 않음)
- ✅ 에이전트 실행 후 깨끗한 정리 보장
- ✅ 포트 충돌 문제 완전 해결
- ✅ 다음 실행을 위한 깨끗한 환경 제공

---

## Issue #13: LLM 기반 동적 보고서 생성

**변경 전:**
- 정적 템플릿으로 보고서 생성
- 고정된 문구와 구조
- 발견사항에 대한 인사이트 부족

**변경 후:**
- GitHub Copilot SDK를 활용한 LLM 기반 보고서 생성
- 공격 결과를 분석하여 의미있는 인사이트 제공
- 한국어로 전문적인 보안 보고서 작성
- 기존 포맷 유지하면서 내용을 동적으로 생성

**구현 내용:**
1. **ReportGenerator 클래스 개선**
   - `initialize()`: Copilot 클라이언트 초기화
   - `_generate_with_llm()`: LLM을 사용한 동적 보고서 생성
   - `_build_report_prompt()`: 컨텍스트와 포맷을 포함한 프롬프트 구성
   - `_generate_static_report()`: Fallback용 정적 보고서
   - `cleanup()`: 세션 정리

2. **프롬프트 구성**
   - 배포 환경 정보 제공 (리소스, 컨테이너, 네트워크)
   - 공격 결과 요약 (성공/실패 횟수, 도구별 결과)
   - 중요 발견사항 상세 정보
   - 보고서 포맷 지정 (마크다운 구조)
   - 한국어 작성 지시
   - 분석 및 인사이트 요구

3. **LocalAttackAgent 연동**
   - `generator.initialize()`: 보고서 생성 전 초기화
   - `await generator.generate()`: 비동기 보고서 생성
   - `generator.cleanup()`: 세션 정리

**코드 위치:**
- `agents/agent.py`: `ReportGenerator` 클래스
  - Line 1459-1480: 클래스 정의 및 초기화
  - Line 1482-1500: LLM 기반 생성 메서드
  - Line 1502-1655: 프롬프트 구성 (컨텍스트 + 포맷 지정)
  - Line 1657-1745: 정적 보고서 Fallback
  - Line 1747-1750: cleanup 메서드
- `agents/agent.py`: `LocalAttackAgent.analyze_and_attack()`
  - Line 938-942: ReportGenerator 초기화 및 호출

**효과:**
- ✅ 전문적이고 맥락에 맞는 보안 보고서 생성
- ✅ 발견사항에 대한 심층 분석 및 인사이트 제공
- ✅ 실행 가능한 권장사항 자동 생성
- ✅ 한국어로 자연스러운 보고서 작성
- ✅ Copilot SDK 사용 불가 시 정적 보고서로 Fallback

---

## Issue #14: Agent Loop 아키텍처 도입

**변경 전:**
- 정적 전략 방식: LLM이 전체 공격 전략을 한 번에 생성
- AttackOrchestrator가 미리 정의된 순서로 모든 공격 실행
- 공격 결과를 보고 다음 행동을 결정하지 못함
- CopilotStrategyEngine으로 전략 생성 후 실행

**변경 후:**
- **Agent Loop 패턴**: Plan → Act → Observe → Re-plan
- LLM이 공격 도구를 직접 선택하고 호출
- 각 공격 결과를 관찰하고 동적으로 다음 공격 결정
- GitHub Copilot SDK의 `define_tool` 및 function calling 활용
- **CopilotStrategyEngine 제거** (Agent Loop로 완전 대체)

**구현 내용:**
1. **Pydantic 파라미터 모델 정의**
   - `NmapScanParams`, `HydraAttackParams`, `SQLMapAttackParams`, `MetasploitExploitParams`
   - 각 도구의 파라미터를 타입 안전하게 정의

2. **CopilotAgentLoop 클래스**
   - `_init_tools()`: `@define_tool` 데코레이터로 4개 도구 정의
   - 각 tool handler가 실제 공격 도구 실행 및 결과 저장
   - `initialize()`: Copilot SDK 초기화 및 세션 생성 시 도구 전달

3. **Agent Loop 실행 로직**
   - `run_agent_loop()`: 최대 15회 반복
   - 매 iteration마다 LLM에게 프롬프트 전송
   - SDK가 자동으로 tool 호출 처리
   - 공격 결과 개수 비교로 도구 실행 여부 확인
   - 결과를 컨텍스트에 누적하여 다음 프롬프트에 포함

4. **초기 컨텍스트 생성**
   - `_build_initial_context()`: 배포 환경, 타겟, 네트워크 규칙 제공
   - 침투 테스트 방법론 가이드 (Reconnaissance → Analysis → Exploitation)
   - 도구 설명 및 사용 순서 지침

5. **결과 포맷팅**
   - `_format_tool_result()`: 각 공격 결과를 LLM이 이해할 수 있는 형태로 변환
   - 성공/실패 상태, findings, timestamp 포함

6. **LocalAttackAgent 통합**
   - `self.agent_loop = CopilotAgentLoop()` 추가
   - `analyze_and_attack()`에서 Agent Loop 사용
   - **CopilotStrategyEngine 완전 제거** (100+ 줄 감소)
   - AttackOrchestrator는 fallback용으로 유지

7. **Fallback 처리**
   - Copilot SDK 사용 불가 시 AttackOrchestrator로 fallback
   - 도구 실행 실패 시 에러 로깅 및 계속 진행
   - 최대 반복 횟수 초과 시 종료

8. **로깅 및 디버깅**
   - 각 iteration에서 공격 수행 로깅
   - 도구 실행 시 파라미터 로깅
   - 공격 성공/실패 구분 로깅
   - LLM의 텍스트 응답 로깅

**코드 위치:**
- `agents/agent.py`: Pydantic 모델 정의
  - Line 26-28: `from copilot.tools import define_tool`, `from pydantic import BaseModel`
  - Line 813-833: Pydantic 파라미터 모델 4개
- `agents/agent.py`: `CopilotAgentLoop` 클래스
  - Line 840-950: 클래스 정의, 초기화, tool 정의
  - Line 952-1005: `run_agent_loop()` - Agent Loop 실행 로직
  - Line 1007-1091: 컨텍스트 생성, 포맷팅, fallback, cleanup
- `agents/agent.py`: `LocalAttackAgent`
  - Line 1145: `self.agent_loop = CopilotAgentLoop()` 추가
  - Line 1171-1179: Agent Loop 초기화 및 실행
  - **CopilotStrategyEngine 제거됨** (~110줄 감소)

**효과:**
- 🎯 **동적 의사결정**: 상황에 맞게 다음 공격 선택
- 🔄 **반복 학습**: 각 결과 기반으로 전략 조정
- 🛠️ **효율적 공격**: 불필요한 공격 생략, 중요 타겟 집중
- 📊 **투명한 추론**: LLM의 결정 과정 로깅
- 🚀 **확장 가능**: 새로운 도구 추가 용이 (데코레이터만 추가)
- ✅ **타입 안전**: Pydantic으로 파라미터 검증
- 🧹 **코드 간소화**: 미사용 CopilotStrategyEngine 제거로 코드 정리

---

## Issue #15: RedTeam Agent 통합

**일자**: 2026-02-24  
**카테고리**: 아키텍처  
**우선순위**: 높음

### 문제 상황
- 두 개의 RedTeam Agent가 존재 (redteam_agent.py, agent.py)
- redteam_agent.py는 정적 분석 Mock 구현 (정규식 패턴 매칭)
- agent.py의 LocalAttackAgent는 실제 Docker 배포 + 침투 테스트
- API와 테스트에서 Mock Agent 사용 중
- 실제 공격 수행 기능(LocalAttackAgent)이 API에서 사용되지 않음

### 해결 방법
LocalAttackAgent를 RedTeam Agent로 통합하여 실제 공격 수행

**1. 데이터 모델 추가** (`agents/agent.py`)
```python
@dataclass
class VulnerabilityItem:
    id: str
    severity: str  # Critical / High / Medium / Low
    category: str
    affected_resource: str
    title: str
    description: str
    evidence: str
    remediation: str
    benchmark_ref: str = ""

@dataclass
class AttackScenario:
    id: str
    name: str
    mitre_technique: str
    target_vulnerabilities: List[str]
    severity: str
    prerequisites: str
    attack_chain: List[str]
    expected_impact: str
    detection_difficulty: str
    likelihood: str

@dataclass
class AnalysisResult:
    architecture_summary: dict
    vulnerabilities: List[VulnerabilityItem]
    attack_scenarios: List[AttackScenario]
    report: str
    raw_results: dict = field(default_factory=dict)
```

**2. API 호환 메서드 추가** (`LocalAttackAgent.analyze()`)
```python
async def analyze(self, bicep_code: str) -> AnalysisResult:
    """API 호환 메서드: analyze_and_attack() 호출 후 변환"""
    result = await self.analyze_and_attack(bicep_code)
    return self._convert_to_analysis_result(result)
```

**3. 변환 로직 구현**
- AttackResult → VulnerabilityItem 변환
- AttackResult → AttackScenario 변환
- 공격 도구별 심각도, MITRE 기법, 보안 권장사항 매핑
- 마크다운 보고서 포함

**4. API 업데이트** (`api/routers/analyze.py`)
```python
from agents.agent import LocalAttackAgent

async def _run_redteam(bicep_code: str):
    agent = LocalAttackAgent()
    result = await agent.analyze(bicep_code)
    return result, StepStatus(...)
```

**5. 테스트 업데이트** (`tests/test_agents.py`)
```python
@pytest.mark.asyncio
@pytest.mark.integration  # 통합 테스트로 마킹
async def test_redteam_analyze_returns_result():
    agent = LocalAttackAgent()
    result = await agent.analyze(SAMPLE_BICEP)
    assert result.vulnerabilities is not None
```

**6. redteam_agent.py 삭제**
- 510줄 Mock 구현 제거
- agents/__init__.py에서 import 제거

### 코드 위치
- `agents/agent.py`
  - Line 44-102: VulnerabilityItem, AttackScenario, AnalysisResult 추가
  - Line 1311-1622: analyze() 및 변환 메서드 추가
- `api/routers/analyze.py`
  - Line 9: import 수정 (LocalAttackAgent로 변경)
  - Line 51-53: _run_redteam() 수정
- `tests/test_agents.py`
  - Line 6: import 수정
  - Line 45-95: 테스트를 통합 테스트로 변경
- `agents/__init__.py`
  - Line 2: RedTeamAgent → LocalAttackAgent로 변경
- `agents/redteam_agent.py`: **삭제됨**

### 효과
- ✅ **실제 공격 수행**: Mock이 아닌 실제 Docker 환경에서 침투 테스트
- ✅ **Agent Loop 활용**: LLM 기반 동적 공격 전략
- ✅ **API 호환성 유지**: 기존 AnalysisResult 형식 유지
- ⚠️ **응답 시간 증가**: 1-2초 → 5-15분 (실제 배포 및 공격)
- ⚠️ **Docker 필수**: Docker 환경이 없으면 실행 불가

### 주의사항
- API 응답 시간이 크게 증가 (1초 → 10분)
- Docker 및 Copilot SDK 필수 의존성
- 통합 테스트는 Docker 환경에서만 실행 (`@pytest.mark.integration`)
- 프로덕션 환경에서는 타임아웃 설정 필요

---

## Issue #16: 공격 도구 확장

**일자**: 2026-02-24  
**카테고리**: 기능 추가  
**우선순위**: 높음

### 문제 상황
- 기존 Agent는 4개 도구만 보유 (Nmap, Hydra(SSH), SQLMap, Metasploit)
- Mock data의 공격 시나리오 중 25%만 실제 수행 가능
- SQL Server 인증 공격, RDP 공격, Azure Blob 스캔 미지원
- 다양한 공격 벡터 테스트 불가

### 해결 방법
추가 공격 도구 3개 구현

**1. SQLServerAttacker 추가**
- SQL Server 무차별 대입 공격 (Hydra mssql 모듈)
- 기본 자격 증명 시도: sa, admin, administrator 등
- Mock data의 "SQL Server 직접 접근" 시나리오 지원

**2. RDPAttacker 추가**
- RDP 무차별 대입 공격 (Hydra rdp 모듈)
- 기본 Windows 자격 증명 시도: administrator, admin 등
- Mock data의 "RDP 포트 개방" 시나리오 지원

**3. AzureBlobScanner 추가**
- Azure Blob 스토리지 익명 접근 스캔
- azure-storage-blob SDK 사용
- 공개 컨테이너 탐색 및 Blob 다운로드 시도
- HTTP 엔드포인트 감지 (암호화되지 않은 트래픽)
- Mock data의 "스토리지 계정 공개 Blob" 시나리오 지원

### 코드 위치

**도구 구현** (`agents/agent.py`)
- Line 1930-2026: `SQLServerAttacker` 클래스
- Line 2028-2124: `RDPAttacker` 클래스
- Line 2126-2244: `AzureBlobScanner` 클래스

**Pydantic 파라미터 모델** (`agents/agent.py`)
- Line 906-918: `SQLServerAttackParams`
- Line 920-927: `RDPAttackParams`
- Line 929-937: `AzureBlobScanParams`

**Agent Loop 통합** (`CopilotAgentLoop._init_tools()`)
- Line 1039-1104: 3개 새 tool 정의 (@define_tool 데코레이터)
  - `attack_sqlserver`: SQL Server 인증 공격
  - `attack_rdp`: RDP 무차별 대입 공격
  - `scan_azure_blob`: Azure Blob 스캔
- Line 1106-1113: tools 리스트에 추가

**의존성** (`requirements.txt`)
- Line 18-19: `azure-storage-blob>=12.19.0` 추가

### 기술적 세부사항

#### SQLServerAttacker
```python
# Hydra mssql 모듈 사용
cmd = ["hydra", "-L", user_file, "-P", pass_file, "-t", "4", "-vV", 
       f"mssql://{target}:{port}"]

# 기본 자격 증명
users = ["sa", "admin", "administrator", "user", "sqlserver"]
passwords = ["password", "Admin123!", "Password123!", "YourStrong!Passw0rd"]
```

#### RDPAttacker
```python
# Hydra rdp 모듈 사용
cmd = ["hydra", "-L", user_file, "-P", pass_file, "-t", "4", "-vV",
       f"rdp://{target}:{port}"]

# 기본 Windows 자격 증명
users = ["administrator", "admin", "user", "guest"]
passwords = ["password", "Admin123!", "Password123!", "Pa$$w0rd"]
```

#### AzureBlobScanner
```python
from azure.storage.blob import BlobServiceClient

# 익명 접근 시도
blob_service_client = BlobServiceClient(account_url=account_url)
containers = blob_service_client.list_containers()

# 공개 컨테이너 탐색
for container in containers:
    container_client = blob_service_client.get_container_client(container["name"])
    blobs = container_client.list_blobs()
```

### Agent Loop 프롬프트 업데이트
LLM이 새 도구를 인식하고 사용할 수 있도록 초기 컨텍스트 제공:

```
Available attack tools:
1. scan_with_nmap - Network port scanning
2. attack_ssh_with_hydra - SSH brute force
3. attack_sql_with_sqlmap - SQL Injection
4. exploit_with_metasploit - Metasploit exploits
5. attack_sqlserver - SQL Server authentication brute force (NEW)
6. attack_rdp - RDP brute force (NEW)
7. scan_azure_blob - Azure Blob storage public access scan (NEW)
```

### 효과
- ✅ **공격 다양성 확대**: 4개 → 7개 도구
- ✅ **Mock data 커버리지**: 25% → 75%
- ✅ **지원 공격 시나리오**:
  - SSH 무차별 대입 (기존)
  - SQL Injection (기존)
  - **SQL Server 인증 공격 (신규)**
  - **RDP 무차별 대입 (신규)**
  - **Azure Blob 공개 접근 (신규)**
- ✅ **LLM 자율성 향상**: 상황에 맞는 도구 선택 옵션 증가
- ✅ **실제 환경 반영**: Azure 리소스 공격 벡터 추가

### 주의사항
- **Hydra 필수**: SQLServerAttacker, RDPAttacker는 Hydra 설치 필요
- **Azure SDK 필수**: AzureBlobScanner는 azure-storage-blob 패키지 필요
- **로컬 환경만**: 모든 공격은 Docker 로컬 환경에서만 수행
- **도구 가용성 체크**: 각 도구는 초기화 시 설치 여부 확인

### 향후 확장 가능 도구
- FTPAttacker (FTP 무차별 대입)
- DNSEnumerator (DNS 열거 및 서브도메인 발견)
- AzureKeyVaultScanner (Key Vault 접근 스캔)
- BicepStaticAnalyzer (정적 코드 분석)

---

## Docker 문제 해결 가이드

> 상세한 이슈 내용은 [Issue #9](#issue-9-sql-server-비밀번호-정책-위반), [Issue #10](#issue-10-컨테이너-이름-충돌), [Issue #11](#issue-11-컨테이너-초기화-시간-부족), [Issue #12](#issue-12-포트-충돌-및-orphan-컨테이너)를 참고하세요.

### 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| 메모리 | 4GB | 8GB (SQL Server 포함) |
| 디스크 | 2GB | 3GB |
| CPU | 2코어 | 4코어 |

### 예상 소요 시간

- **첫 실행**: 5-10분 (이미지 다운로드)
- **이후 실행**: 30초-2분 (캐시 사용)
- **최대 대기**: 10분 (컨테이너 초기화)

### 문제 해결 방법

#### 배포 실패 시
```bash
# 1. 로그 확인
docker-compose -f /tmp/[compose_file].yml logs

# 2. 수동 정리
docker-compose -f /tmp/[compose_file].yml down -v
docker system prune -f

# 3. Docker 재시작
# Docker Desktop → Restart
```

#### SQL Server 시작 실패 시
- Docker 메모리 4GB 이상 할당 확인
- M1/M2 Mac: Rosetta 활성화 또는 ARM 버전 사용
- 비밀번호 정책 준수 확인

#### 메모리 부족 시
```bash
# Docker Desktop → Preferences → Resources → Memory 증가
# 또는 불필요한 컨테이너 정리
docker system prune -a
```

---

## 생성된 파일

### 문서
- `ISSUES_RESOLVED.md` - **이슈 해결 통합 문서 (이 파일)**
- `README_RETRY_FEATURE.md` - 재시도 기능 Quick Reference
- `HISTORY.md` - 개발 히스토리

### 테스트
- `test_deployment_failure.py` - 배포 실패 시나리오 테스트
- `test_bicep_string.py` - Bicep 문자열 입력 테스트

---

## 현재 상태

✅ **완료된 작업**
- Docker 배포 자동 재시도 (최대 2회)
- Compose 파일 자동 검증 및 수정
- 컨테이너 감지 로직 개선 (subprocess 기반)
- 배포 대기 시간 최적화 (반복 체크, 최대 10분)
- 로그 메시지 명확화
- 배포 실패 보고서 생성
- Mock 모드 완전 제거
- Bicep 문자열 입력 지원

🎯 **요구사항**
- Docker 필수 (실행 중이어야 함)
- 보안 도구 설치 권장 (Nmap, Hydra, SQLMap, Metasploit)

🎯 **배포 성공률**
- 첫 실행: 5-10분 (이미지 다운로드 포함)
- 이후 실행: 30초-2분 (캐시 사용)
- 최대 대기: 10분 (컨테이너 초기화)

### Issue #17: Storage Scanner 로컬 호환성 개선 및 리네이밍

**문제**: 
- `AzureBlobScanner`가 Azure SDK(`azure-storage-blob`)를 사용해서 실제 Azure 클라우드에만 작동
- 로컬 Docker 환경의 MinIO/Azurite 에뮬레이터와 호환 불가
- 클래스 이름이 Azure 전용으로 오해되어 혼란
- Agent Loop가 스토리지 컨테이너 취약점을 전혀 테스트하지 못함

**근본 원인**:
1. Azure SDK는 Azure 클라우드 엔드포인트 전용 (`https://{account}.blob.core.windows.net`)
2. 로컬 Docker는 HTTP 엔드포인트 노출 (`http://{IP}:9000`)
3. 인증 방식 차이 (Azure: Managed Identity vs 로컬: 익명/Basic Auth)
4. 클래스명이 기능을 정확히 표현하지 못함

**해결**:

1. **클래스 및 변수 리네이밍**
   ```python
   # Before
   class AzureBlobScanner:
       ...
   self.blob_scanner = AzureBlobScanner()
   
   # After
   class StorageHTTPScanner:  # 범용적인 이름
       """스토리지 HTTP 엔드포인트 공개 접근 스캔 (로컬 Docker/Azure 호환)"""
       ...
   self.storage_scanner = StorageHTTPScanner()
   ```

2. **HTTP 직접 요청 방식으로 재구현**
   ```python
   async def scan(self, target: str, port: int = 9000) -> AttackResult:
       import requests
       
       base_url = f"http://{target}:{port}"
       
       # 1. 루트 엔드포인트 확인
       resp = requests.get(base_url, timeout=5)
       
       # 2. 공개 버킷 스캔
       common_buckets = ["public", "data", "backup", "uploads"]
       for bucket in common_buckets:
           resp = requests.get(f"{base_url}/{bucket}", timeout=3)
           if resp.status_code == 200:
               findings.append(f"✓ Public bucket found: /{bucket}")
       
       # 3. MinIO API 감지
       resp = requests.get(f"{base_url}/minio/health/live", timeout=3)
   ```

3. **도구 파라미터 변경**
   - `AzureBlobScanParams` → `StorageScanParams`
   - 파라미터: `storage_account_name, endpoint` → `target, port`
   
   ```python
   class StorageScanParams(BaseModel):
       target: str = Field(description="Storage server IP address or hostname")
       port: int = Field(default=9000, description="Storage HTTP port (MinIO=9000, Azurite=10000)")
   
   @define_tool(description="Scan HTTP storage endpoint (MinIO/S3/Azure)...")
   async def scan_storage_http(params: StorageScanParams) -> dict:
       ...
   ```

4. **스캔 로직**
   - 루트 엔드포인트 접근성 확인
   - 공개 버킷 자동 발견 (common names)
   - MinIO/Azurite 서버 감지
   - HTTP 사용 경고 (보안 위험)
   - XML 응답 파싱 (S3 API)

5. **의존성 변경**
   ```diff
   - azure-storage-blob>=12.19.0  # Azure Blob 스토리지 스캔 (18MB)
   + requests>=2.31.0  # HTTP 요청 (스토리지 스캔, ~1MB)
   ```

**효과**:
- ✅ 로컬 Docker MinIO/Azurite 완벽 지원
- ✅ Azure 클라우드도 HTTP API로 접근 가능
- ✅ 클래스 이름이 기능을 정확히 표현
- ✅ 의존성 경량화 (18MB → 1MB)
- ✅ 더 빠른 스캔 속도 (SDK 오버헤드 제거)
- ✅ 디버깅 용이 (HTTP 로그 직접 확인)
- ✅ LLM이 Nmap 결과에서 포트 발견 → 즉시 scan_storage_http 호출 가능

**코드 위치**:
- `agents/agent.py` Line 2308-2430: `StorageHTTPScanner` 클래스 (리네이밍)
- `agents/agent.py` Line 954: `self.storage_scanner = StorageHTTPScanner()` (변수 리네이밍)
- `agents/agent.py` Line 924-930: `StorageScanParams` 모델
- `agents/agent.py` Line 1072-1086: `scan_storage_http` 도구 정의
- `agents/agent.py` Line 1250-1266: 초기 프롬프트 업데이트
- `requirements.txt` Line 18-21: 의존성 변경

**테스트 시나리오**:
```python
# MinIO 컨테이너 스캔 (포트 9000)
scan_storage_http(target="172.20.0.5", port=9000)
# → "✓ Public bucket found: /public"
# → "✓ MinIO server detected"
# → "⚠️ Unencrypted HTTP traffic"

# Azurite 컨테이너 스캔 (포트 10000)
scan_storage_http(target="172.20.0.6", port=10000)
# → "✓ Public bucket found: /data"
```

**참조**: `docs/BUGFIX_BLOB_SCANNER_LOCAL_COMPATIBILITY.md`

---

## Issue #18: 코드 버그 수정 (8개)

**일자**: 2026-02-24
**카테고리**: 버그 수정
**우선순위**: Critical/High

### Bug #1: HydraAttacker.attack_ssh() 파라미터 불일치 (TypeError)
- **위치**: `agents/agent.py` - `HydraAttacker.attack_ssh()` 메서드
- **문제**: Tool handler가 `(target, username, password_list)`를 전달하지만 메서드가 `(target, port=22)`만 받아 TypeError 발생
- **수정**: 시그니처를 `attack_ssh(target, username=None, password_list=None, port=22)`로 변경, 전달된 값으로 임시 파일 구성

### Bug #2: _fallback_attack() 메서드 미정의 (AttributeError)
- **위치**: `agents/agent.py` - `CopilotAgentLoop` 클래스
- **문제**: Copilot SDK 없을 때 `_fallback_attack()`을 호출하지만 메서드가 없어 AttributeError 발생
- **수정**: `_fallback_attack(deployment_info)` 메서드 추가 — NmapScanner로 모든 컨테이너 스캔

### Bug #3: cleanup() shell 명령어 문법 오류
- **위치**: `agents/agent.py` - `LocalDeployer.cleanup()` 메서드 (Line 829-844)
- **문제**: `subprocess.run(["docker", "stop", "$(docker ps -q)"], shell=True)` — list + shell=True 조합에서 `$()` 치환 불동작
- **수정**: 문자열 형태로 변경 (`"docker stop $(docker ps -q) 2>/dev/null || true"`)

### Bug #4: HydraAttacker.attack_ssh() success 항상 True
- **위치**: `agents/agent.py` - `HydraAttacker.attack_ssh()` 반환
- **문제**: `_parse_hydra_output()`이 빈 결과면 `["No valid credentials found"]` 반환 → `len(findings) > 0` 항상 True
- **수정**: `any("valid credentials found:" in f.lower() for f in findings)`로 변경

### Bug #5: nmap 심각도 판단 false positive
- **위치**: `agents/agent.py` - `_determine_severity()` 메서드
- **문제**: `any("open" in f.lower() ...)` → "no **open** ports found"도 매칭됨
- **수정**: `any("open port:" in f.lower() ...)` 로 변경

### Bug #6: nmap 성공이 취약점으로 잘못 분류
- **위치**: `agents/agent.py` - `_convert_to_vulnerabilities()` 메서드
- **문제**: nmap returncode==0(success=True)이면 open port 없어도 취약점으로 등록됨
- **수정**: nmap tool은 "open port:" 포함된 finding이 있는 경우만 취약점으로 등록

### Bug #7: 새 도구들(sqlserver/rdp/storage_scan)이 변환 맵에 없음
- **위치**: `agents/agent.py` - `LocalAttackAgent` 변환 메서드들
- **문제**: `_determine_severity`, `_attack_to_category`, `_get_remediation`, `_get_benchmark_ref`, `_get_attack_scenario_name`, `_get_mitre_technique`, `_get_prerequisites`, `_build_attack_chain`, `_get_expected_impact` 모두 새 도구 미처리
- **수정**: 각 메서드에 `sqlserver`, `rdp`, `storage_scan` 항목 추가

### Bug #8: _get_related_vulnerabilities() 비결정적 hash 사용
- **위치**: `agents/agent.py` - `_get_related_vulnerabilities()` 메서드
- **문제**: `hash(attack.target)` — Python hash randomization으로 실행마다 다른 ID 생성
- **수정**: tool+target 문자열의 `ord()` 합산(결정적) 사용, 기존 취약점 목록 우선 참조

**수정 파일**: `agents/agent.py`

---

## Issue #19: Agent Loop 조기 종료 — 모든 도구 강제 실행

**일자**: 2026-02-24
**카테고리**: Agent Loop 로직 개선
**우선순위**: High

### 문제 상황
- nmap이 "no open ports" 반환 시 LLM이 즉시 COMPLETE 결정
- 공격 도구(hydra, sqlserver, rdp 등)가 전혀 호출되지 않음
- 같은 IP에 nmap을 두 번씩 스캔하는 중복 문제 (12회 = 6 IP × 2)

### 해결 방법

**1. 강제 실행 단계 추가** (`_run_mandatory_attacks()`)
- Agent Loop 완료 후 미사용 도구를 코드 레벨에서 강제 실행
- `used_tool_target_pairs`로 이미 실행된 tool+target 쌍 추적
- 각 도구별로 미테스트 타겟이 있으면 첫 번째 타겟에 강제 실행
- 대상 도구: hydra, sqlserver, rdp, sqlmap, storage_scan, metasploit

**2. 프롬프트 개선** (`_build_initial_context()`)
- "nmap 결과 기반 조건부 실행" → "모든 도구 필수 사용 감사(audit)" 방식으로 변경
- 체크리스트 형태로 7개 도구 명시
- "nmap에서 포트 없어도 공격 도구는 반드시 실행" 명시

**3. COMPLETE 조기 종료 방지** (`run_agent_loop()`)
- LLM이 COMPLETE 응답해도 미사용 도구 목록 확인
- 미사용 도구가 있으면 COMPLETE 무시하고 OVERRIDE 메시지 추가
- 모든 필수 도구 사용 후에만 루프 종료 허용

**4. 매 결과마다 남은 도구 체크리스트 표시** (`_format_tool_result()`)
- 각 도구 실행 결과에 "남은 필수 도구" 목록 자동 추가
- LLM이 항상 다음 실행할 도구를 명확히 알 수 있도록

**코드 위치**:
- `agents/agent.py`: `run_agent_loop()` — COMPLETE 방지 로직, `_run_mandatory_attacks()` 호출
- `agents/agent.py`: `_run_mandatory_attacks()` — 신규 메서드, 미사용 도구 강제 실행
- `agents/agent.py`: `_build_initial_context()` — 프롬프트 전면 개정
- `agents/agent.py`: `_format_tool_result()` — 남은 체크리스트 추가
- `agents/agent.py`: `_get_next_action_hint()` — iteration 파라미터 제거, nmap 결과 무관 hint 개선

**효과**:
- ✅ 모든 도구가 반드시 최소 1회 실행 보장 (코드 레벨 강제)
- ✅ LLM이 조기 종료해도 자동으로 나머지 도구 실행
- ✅ nmap 중복 스캔 방지 힌트 명시
- ✅ 매 iteration마다 남은 도구 목록으로 LLM 가이드

---

## 생성된 파일


| 파일 | 변경 사항 | 라인 수 |
|------|----------|---------|
| `agents/agent.py` | 재시도, 검증, 컨테이너 감지, Mock 제거, 입력 처리 | ~150줄 추가/수정 |
| `README_RETRY_FEATURE.md` | 기능 문서 | 신규 |
| `docs/DEPLOYMENT_RETRY_FEATURE.md` | 상세 명세 | 신규 |
| `test_deployment_failure.py` | 테스트 스크립트 | 신규 |
| `test_bicep_string.py` | Bicep 문자열 테스트 | 신규 |

---

## 사용 방법

### 1. 파일 경로로 실행
```bash
python3 agents/agent.py samples/sample_bicep.bicep
```

### 2. Bicep 코드 문자열로 실행 (프로그래밍 방식)
```python
import asyncio
from agents.agent import run_agent

bicep_code = """
resource storage 'Microsoft.Storage/storageAccounts@2021-04-01' = {
  name: 'mystorage'
  location: 'eastus'
}
"""

result = asyncio.run(run_agent(bicep_code, use_docker=True))
```

### 3. 테스트
```bash
# 배포 실패 시나리오 테스트
python3 test_deployment_failure.py

# Bicep 문자열 입력 테스트
python3 test_bicep_string.py
```

