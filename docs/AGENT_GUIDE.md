# Local Attack Agent 사용 가이드

## 개요

Local Attack Agent는 Bicep 코드로 정의된 Azure 아키텍처를 로컬 환경(Docker Compose)에서 구현하고, 실제 보안 공격을 자동으로 수행하는 독립적인 Agent입니다.

### 핵심 기능

1. **Bicep 파싱**: Azure 리소스 정의 추출 및 분석
2. **로컬 배포**: Docker Compose를 통한 컨테이너 환경 구축
3. **자동 공격**: Nmap, Hydra, SQLMap, Metasploit을 활용한 침투 테스트
4. **AI 전략 수립**: GitHub Copilot SDK를 통한 동적 공격 전략
5. **보고서 생성**: 마크다운 형식의 상세 분석 보고서

## 설치 요구사항

### 필수 요구사항

- Python 3.10 이상
- Docker & Docker Compose (실제 배포 시)

### Python 패키지

```bash
pip install docker pyyaml
```

### 🔧 보안 도구 설치 (실제 공격 실행 시)

Agent를 Mock 모드가 아닌 **실제 공격 도구**로 실행하려면 다음 도구들이 필요합니다:

#### macOS (Homebrew 사용)

```bash
# 전체 설치 (추천)
brew install nmap hydra sqlmap

# 또는 개별 설치
brew install nmap      # 포트 스캔 (필수) - 1-2분
brew install hydra     # SSH/RDP 무차별 대입 - 1-2분
brew install sqlmap    # SQL Injection 테스트 - 1-2분
```

#### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y nmap hydra sqlmap
```

#### 설치 확인

```bash
# 설치된 도구 버전 확인
nmap --version
hydra -h | head -5
sqlmap --version
```

**설치 완료 후**: Agent를 실행하면 Mock 대신 실제 도구가 동작합니다!

```bash
python agents/agent.py samples/sample_bicep.bicep
# 로그에서 "WARNING - Nmap 미설치" 대신 실제 스캔 진행을 확인
```

### Metasploit (선택적, 고급 사용자)

Metasploit은 크고 설치가 복잡하여 기본 테스트에는 불필요합니다.

```bash
# Homebrew를 통한 설치 (간단하지만 구버전일 수 있음)
brew install metasploit

# 또는 공식 인스톨러 (권장)
# https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html
```

> **Note**: Metasploit 없이도 Agent의 대부분 기능은 정상 동작합니다.

```bash
pip install github-copilot-sdk
# 또는
pip install copilot
```

> **Note**: GitHub Copilot SDK가 없어도 Agent는 Fallback 모드로 동작합니다.

## 빠른 시작

### 1. 기본 실행

```bash
cd /path/to/works-on-my-machine
source .venv/bin/activate

python agents/agent.py samples/sample_bicep.bicep
```

### 2. Python 스크립트에서 사용

```python
import asyncio
from agents.agent import LocalAttackAgent

async def main():
    agent = LocalAttackAgent(use_docker=False)  # Docker 없이 Mock 모드
    
    # Bicep 코드 읽기
    with open('samples/sample_bicep.bicep', 'r') as f:
        bicep_code = f.read()
    
    # 분석 및 공격 실행
    result = await agent.analyze_and_attack(bicep_code)
    
    # 결과 출력
    print(f"Success: {result['success']}")
    print(f"Attacks: {result['attacks_executed']}")
    print(f"Critical Findings: {result['critical_findings']}")
    
    # 보고서 저장
    with open('attack_report.md', 'w') as f:
        f.write(result['report'])
    
    print("보고서가 attack_report.md에 저장되었습니다.")

asyncio.run(main())
```

### 3. Docker를 사용한 실제 배포

```python
agent = LocalAttackAgent(use_docker=True)  # Docker 사용
result = await agent.analyze_and_attack(bicep_code)

# 배포 환경 정리
agent.cleanup()
```

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                  LocalAttackAgent                       │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐ │
│  │ BicepParser  │──▶│ResourceMapper│──▶│DockerComposer│ │
│  └──────────────┘   └──────────────┘   └────────────┘ │
│         │                                      │        │
│         ▼                                      ▼        │
│  ┌──────────────┐                      ┌──────────────┐│
│  │NetworkConfig │                      │LocalDeployer ││
│  └──────────────┘                      └──────────────┘│
│         │                                      │        │
│         │           ┌──────────────────┐       │        │
│         └──────────▶│ CopilotStrategy  │◀──────┘        │
│                     │     Engine       │                │
│                     └──────────────────┘                │
│                             │                           │
│                             ▼                           │
│                   ┌──────────────────┐                  │
│                   │AttackOrchestrator│                  │
│                   └──────────────────┘                  │
│                             │                           │
│         ┌───────────────────┼───────────────────┐       │
│         ▼                   ▼                   ▼       │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐      │
│  │  Nmap    │      │  Hydra   │      │ SQLMap   │      │
│  │ Scanner  │      │ Attacker │      │ Attacker │      │
│  └──────────┘      └──────────┘      └──────────┘      │
│         │                   │                   │       │
│         └───────────────────┼───────────────────┘       │
│                             ▼                           │
│                   ┌──────────────────┐                  │
│                   │ ResultAnalyzer   │                  │
│                   └──────────────────┘                  │
│                             │                           │
│                             ▼                           │
│                   ┌──────────────────┐                  │
│                   │ ReportGenerator  │                  │
│                   └──────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

## 주요 클래스

### BicepParser

Bicep 코드를 파싱하여 Azure 리소스 정의를 추출합니다.

**지원 리소스 타입**:
- Virtual Machines (VM)
- Network Security Groups (NSG)
- Public IP Addresses
- Virtual Networks (VNet)
- Storage Accounts
- SQL Servers & Databases
- Web Apps (App Service)
- Key Vaults
- Network Interfaces

### ResourceMapper

Azure 리소스를 Docker 이미지로 매핑합니다.

**매핑 테이블**:
| Azure 리소스 | Docker 이미지 |
|--------------|---------------|
| VM | ubuntu:22.04 |
| SQL Server | mcr.microsoft.com/mssql/server:2022 |
| Storage Account | minio/minio:latest |
| Web App | nginx:alpine |
| Key Vault | vault:latest |

### AttackOrchestrator

공격 도구들을 조율하여 순차적으로 실행합니다.

**공격 흐름**:
1. Nmap: 포트 스캔 및 서비스 탐지
2. Hydra: SSH/RDP 무차별 대입 공격
3. SQLMap: SQL Injection 테스트
4. Metasploit: 익스플로잇 (선택적)

### CopilotStrategyEngine

GitHub Copilot SDK를 사용하여 동적으로 공격 전략을 수립합니다.

## 출력 형식

### JSON 결과

```json
{
  "success": true,
  "resources_parsed": 12,
  "containers_deployed": 2,
  "attacks_executed": 5,
  "successful_attacks": 2,
  "critical_findings": 14,
  "strategy": { ... },
  "analysis": { ... },
  "report": "# 로컬 환경 침투 테스트 보고서\n...",
  "deployment_info": { ... }
}
```

### 마크다운 보고서

보고서는 다음 섹션을 포함합니다:

1. **경영진 요약**: 공격 결과 개요
2. **배포 환경**: 리소스 및 컨테이너 목록
3. **공격 결과**: 도구별 실행 결과
4. **중요 발견사항**: 취약점 상세
5. **권장사항**: 보안 개선 조치
6. **결론**: 종합 평가

## 고급 사용법

### 커스텀 공격 전략

```python
from agents.agent import AttackOrchestrator, DeploymentInfo

orchestrator = AttackOrchestrator()

# 수동 전략 정의
custom_strategy = {
    "priorities": [
        {"target": "172.20.0.10", "tools": ["nmap", "hydra"]}
    ],
    "sequence": ["nmap_scan", "hydra_ssh"]
}

results = await orchestrator.execute_strategy(
    custom_strategy,
    deployment_info
)
```

### 특정 공격 도구만 실행

```python
from agents.agent import NmapScanner, HydraAttacker

# Nmap만 실행
nmap = NmapScanner()
result = await nmap.scan('172.20.0.10', ports='22,80,443')
print(result.findings)

# Hydra만 실행
hydra = HydraAttacker()
result = await hydra.attack_ssh('172.20.0.10', port=22)
print(result.findings)
```

### Docker Compose 파일 저장

```python
from agents.agent import BicepParser, ResourceMapper, DockerComposer

parser = BicepParser()
resources, network_config = parser.parse(bicep_code)

mapper = ResourceMapper(resources, network_config)
service_mapping = mapper.map_to_docker()

composer = DockerComposer(service_mapping)
compose_yaml = composer.generate_compose_file()

# 파일로 저장
with open('docker-compose.yml', 'w') as f:
    f.write(compose_yaml)
```

## 제한사항

1. **Azure 리소스 매핑**: 모든 Azure 리소스를 완벽하게 1:1 매핑하지는 못합니다.
2. **공격 도구 설치**: Nmap, Hydra, SQLMap 등이 로컬에 설치되어 있어야 합니다.
3. **네트워크 격리**: Docker를 사용하지 않으면 격리된 환경을 제공하지 못합니다.
4. **실행 시간**: Metasploit 등 일부 도구는 실행 시간이 오래 걸릴 수 있습니다.

## 보안 주의사항

⚠️ **경고**: 이 도구는 교육 및 테스트 목적으로만 사용해야 합니다.

- **로컬 환경에서만 실행**: 실제 프로덕션 시스템에 절대 사용하지 마세요.
- **권한 관리**: Docker 및 공격 도구는 관리자 권한이 필요할 수 있습니다.
- **네트워크 격리**: Docker 네트워크를 통해 격리된 환경을 유지하세요.
- **윤리적 사용**: 허가 없이 타인의 시스템을 스캔하거나 공격하지 마세요.

## 문제 해결

### Docker 연결 오류

```
Error: Connection refused to Docker daemon
```

**해결**: Docker Desktop을 실행하거나, `use_docker=False`로 Mock 모드 사용

### 공격 도구 미설치

```
Warning: Nmap not available. Using mock results.
```

**해결**: Homebrew 또는 apt-get으로 도구 설치

### GitHub Copilot SDK 없음

```
Warning: GitHub Copilot SDK not available. Using fallback strategy.
```

**해결**: `pip install github-copilot-sdk` 또는 Fallback 모드 사용

## 예제

### 완전한 워크플로우

```python
import asyncio
from agents.agent import LocalAttackAgent

async def full_workflow():
    # 1. Agent 초기화
    agent = LocalAttackAgent(use_docker=False)
    
    # 2. Bicep 파일 읽기
    with open('samples/sample_bicep.bicep', 'r') as f:
        bicep_code = f.read()
    
    # 3. 분석 및 공격
    result = await agent.analyze_and_attack(bicep_code)
    
    # 4. 결과 확인
    if result['success']:
        print(f"✅ 파싱: {result['resources_parsed']}개 리소스")
        print(f"✅ 배포: {result['containers_deployed']}개 컨테이너")
        print(f"✅ 공격: {result['attacks_executed']}회 실행")
        print(f"⚠️  발견: {result['critical_findings']}개 취약점")
        
        # 5. 보고서 저장
        with open('penetration_test_report.md', 'w') as f:
            f.write(result['report'])
        
        print("\n📄 보고서: penetration_test_report.md")
    else:
        print(f"❌ 오류: {result['error']}")
    
    # 6. 정리 (Docker 사용 시)
    # agent.cleanup()

# 실행
asyncio.run(full_workflow())
```

## 추가 리소스

- [Bicep 문법 가이드](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Docker Compose 문서](https://docs.docker.com/compose/)
- [Nmap 가이드](https://nmap.org/book/man.html)
- [MITRE ATT&CK](https://attack.mitre.org/)

## 기여

이 Agent는 교육 및 연구 목적으로 개발되었습니다. 개선 사항이나 버그 리포트는 이슈로 등록해주세요.

## 라이선스

MIT License - 교육 및 테스트 용도로 자유롭게 사용 가능합니다.
