# 아키텍처 설계

## 구현 범위

### 실제 구현

1. **User Interface (Streamlit)** - 전체 구현
2. **RedTeam Agent** - 전체 구현
3. **API Layer (FastAPI + Gunicorn)** - 전체 구현

### Mock 구현 (추후 실제 전환)

- 파일 전처리 (파싱, BiCep Transform)
- Policy Agent
- Azure Blob Storage 연동
- 워크플로우 오케스트레이터

---

## 전체 파이프라인 흐름

```mermaid
flowchart TB
    subgraph UI["1. User Interface (실제 구현)"]
        UI1[파일 업로드<br/>PDF/PNG/JPG]
        UI2[진행 상태 시각화]
    end

    subgraph Preprocessing["2. 파일 전처리 (Mock)"]
        P1[파일 파싱<br/>큰 파일: 5페이지씩 증분]
        P2[Azure Blob 저장<br/>버전 관리]
        P3[BiCep Transform<br/>LLM 호출 → BiCep 코드 생성]
    end

    subgraph Agents["3. Agent 호출 (워크플로우)"]
        A1[Policy Agent - Mock<br/>Azure Policy 준수 검증]
        A2[RedTeam Agent - 실제 구현<br/>BiCep 분석 / 취약점 탐지<br/>공격 시뮬레이션 / 보고서 생성]
    end

    subgraph Result["4. 결과 표시"]
        R1[취약점 목록]
        R2[공격 시나리오]
        R3[보안 권장사항]
    end

    UI --> Preprocessing
    Preprocessing --> Agents
    A1 --> A2
    Agents --> Result
```

---

## 컴포넌트 상세

### 1. User Interface

**기능 명세:**

1. **파일 업로드** - 지원 포맷: PDF, PNG, JPG
2. **파이프라인 시각화** - 파일 업로드 → 전처리 → BiCep 변환 → Policy 검증 → RedTeam 분석
3. **결과 표시** - RedTeam 보고서 렌더링, 취약점 목록, 보안 권장사항

### 2. RedTeam Agent

**핵심 기능:**

1. **BiCep 코드 분석** - 리소스 구성 이해 및 관계 분석
2. **취약점 탐지** - 보안 설정 오류, 네트워크 노출 위험, 인증/인가 검증, 암호화 누락
3. **공격 시뮬레이션** - 잠재적 공격 벡터 도출, 취약점 악용 시나리오 작성
4. **보고서 생성** - 심각도별 취약점 분류, 공격 시뮬레이션 결과, 보안 개선 권장사항 (마크다운)

### 3. API Layer

**핵심 기능:**

1. **파일 업로드 엔드포인트** - 파일 검증 (크기 20MB, 포맷), 비동기 처리
2. **오케스트레이션** - 전처리 → Policy Agent → RedTeam Agent 순차 호출 및 결과 통합
3. **상태 관리** - `GET /api/v1/status/{task_id}` 진행 상태 조회
4. **에러 핸들링** - 표준화된 에러 응답 및 로깅

---

## API 호출 시퀀스

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant S as Streamlit UI
    participant A as FastAPI
    participant F as File Processor
    participant B as BiCep Transformer
    participant P as Policy Agent
    participant R as RedTeam Agent

    U->>S: 파일 업로드
    S->>A: POST /api/v1/analyze
    A->>F: 파일 전처리
    F-->>A: 파싱 결과
    A->>B: BiCep 변환
    B-->>A: BiCep 코드
    A->>P: Policy 검증
    P-->>A: 검증 결과
    A->>R: RedTeam 분석
    R-->>A: 취약점 보고서
    A-->>S: 분석 결과
    S-->>U: 결과 표시
```

---

## Mock 서비스 명세

Mock 서비스는 실제 구현 전환 전까지 정적 샘플 데이터를 반환합니다.

| 서비스             | 현재 동작                           | 실제 구현 시                             |
| ------------------ | ----------------------------------- | ---------------------------------------- |
| 파일 전처리        | 샘플 BiCep 코드 반환                | 파일 파싱 (5p 증분), Azure Blob 저장     |
| BiCep Transform    | 샘플 BiCep 코드 반환                | LLM 호출하여 아키텍처 → BiCep 변환       |
| Policy Agent       | 패턴 기반 정적 검증                 | MS Agent Framework + Azure Policy 연동   |
| Blob Storage       | 인메모리 딕셔너리 저장              | Azure Blob Storage 연동                  |
