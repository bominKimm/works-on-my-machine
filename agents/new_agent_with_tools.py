"""
Bicep to Docker Compose Converter Agent

GitHub Copilot SDK 기반의 Agent로, Bicep 코드를 읽어서 Docker Compose 파일로 변환합니다.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Annotated, List, Dict, Any
from pydantic import BaseModel, Field

from agent_framework.github import GitHubCopilotAgent

# 기존 agent.py의 컴포넌트 재사용
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.agent import (
    BicepParser,
    ResourceMapper,
    DockerComposer,
    NetworkConfig,
    BicepResource,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# ============================================================
# Tool Input/Output Schemas
# ============================================================


class ReadBicepFileInput(BaseModel):
    """Bicep 파일 읽기 도구 입력"""

    file_path: str = Field(description="Path to the Bicep file to read")


class ReadBicepFileOutput(BaseModel):
    """Bicep 파일 읽기 도구 출력"""

    success: bool
    bicep_code: str | None = None
    error: str | None = None


class ParseBicepInput(BaseModel):
    """Bicep 코드 파싱 도구 입력"""

    bicep_code: str = Field(description="Bicep code content to parse")


class ParseBicepOutput(BaseModel):
    """Bicep 코드 파싱 도구 출력"""

    success: bool
    resources: List[Dict[str, Any]] | None = None
    network_config: Dict[str, Any] | None = None
    error: str | None = None
    warnings: List[str] = []


class GenerateComposeInput(BaseModel):
    """Docker Compose 생성 도구 입력"""

    resources: List[Dict[str, Any]] = Field(description="Parsed Bicep resources")
    network_config: Dict[str, Any] = Field(description="Network configuration")


class GenerateComposeOutput(BaseModel):
    """Docker Compose 생성 도구 출력"""

    success: bool
    compose_yaml: str | None = None
    services: List[str] = []
    error: str | None = None
    warnings: List[str] = []


class SaveComposeFileInput(BaseModel):
    """Docker Compose 파일 저장 도구 입력"""

    compose_yaml: str = Field(description="Docker Compose YAML content")
    output_path: str = Field(
        default="docker-compose.yml", description="Output file path"
    )


class SaveComposeFileOutput(BaseModel):
    """Docker Compose 파일 저장 도구 출력"""

    success: bool
    file_path: str | None = None
    error: str | None = None


class DeployDockerComposeInput(BaseModel):
    """Docker Compose 배포 도구 입력"""

    compose_file_path: str = Field(
        description="Path to the docker-compose.yml file to deploy"
    )


class DeployDockerComposeOutput(BaseModel):
    """Docker Compose 배포 도구 출력"""

    success: bool
    message: str | None = None
    containers: List[str] = []
    error: str | None = None


# ============================================================
# Tool Functions
# ============================================================


def read_bicep_file(
    input_data: Annotated[ReadBicepFileInput, "Input for reading Bicep file"],
) -> ReadBicepFileOutput:
    """
    Bicep 파일을 읽어서 내용을 반환합니다.

    Args:
        input_data: 파일 경로를 포함한 입력

    Returns:
        파일 내용 또는 에러 메시지
    """
    try:
        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = ReadBicepFileInput(**input_data)

        file_path = Path(input_data.file_path)

        if not file_path.exists():
            return ReadBicepFileOutput(
                success=False, error=f"File not found: {input_data.file_path}"
            )

        with open(file_path, "r", encoding="utf-8") as f:
            bicep_code = f.read()

        logger.info(f"✅ Successfully read Bicep file: {input_data.file_path}")
        return ReadBicepFileOutput(success=True, bicep_code=bicep_code)

    except Exception as e:
        logger.error(f"❌ Error reading Bicep file: {e}")
        return ReadBicepFileOutput(success=False, error=str(e))


def parse_bicep(
    input_data: Annotated[ParseBicepInput, "Input for parsing Bicep code"],
) -> ParseBicepOutput:
    """
    Bicep 코드를 파싱하여 리소스와 네트워크 설정을 추출합니다.

    Args:
        input_data: Bicep 코드를 포함한 입력

    Returns:
        파싱된 리소스 목록과 네트워크 설정
    """
    try:
        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = ParseBicepInput(**input_data)

        parser = BicepParser()
        resources, network_config = parser.parse(input_data.bicep_code)

        # BicepResource와 NetworkConfig를 딕셔너리로 변환
        resources_dict = [
            {
                "name": r.name,
                "type": r.type,
                "properties": r.properties,
                "location": r.location,
            }
            for r in resources
        ]

        network_config_dict = {
            "subnets": network_config.subnets,
            "security_rules": network_config.security_rules,
            "public_ips": network_config.public_ips,
        }

        logger.info(f"✅ Successfully parsed {len(resources)} resources")

        warnings = []
        if not resources:
            warnings.append("No Azure resources found in Bicep code")

        return ParseBicepOutput(
            success=True,
            resources=resources_dict,
            network_config=network_config_dict,
            warnings=warnings,
        )

    except Exception as e:
        logger.error(f"❌ Error parsing Bicep code: {e}")
        return ParseBicepOutput(success=False, error=str(e))


def generate_compose(
    input_data: Annotated[GenerateComposeInput, "Input for generating Docker Compose"],
) -> GenerateComposeOutput:
    """
    파싱된 Bicep 리소스를 Docker Compose YAML로 변환합니다.

    Args:
        input_data: 파싱된 리소스와 네트워크 설정

    Returns:
        Docker Compose YAML 문자열
    """
    try:
        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = GenerateComposeInput(**input_data)

        # 딕셔너리를 다시 BicepResource와 NetworkConfig 객체로 변환
        resources = [
            BicepResource(
                name=r["name"],
                type=r["type"],
                properties=r["properties"],
                location=r.get("location", ""),
            )
            for r in input_data.resources
        ]

        network_config = NetworkConfig(
            subnets=input_data.network_config.get("subnets", []),
            security_rules=input_data.network_config.get("security_rules", []),
            public_ips=input_data.network_config.get("public_ips", []),
        )

        # ResourceMapper로 Docker 서비스 매핑
        mapper = ResourceMapper(resources, network_config)
        service_mapping = mapper.map_to_docker()

        # DockerComposer로 YAML 생성
        composer = DockerComposer(service_mapping)
        compose_yaml = composer.generate_compose_file()

        service_names = list(service_mapping.keys())

        logger.info(
            f"✅ Successfully generated Docker Compose with {len(service_names)} services"
        )

        warnings = []
        if len(service_names) == 0:
            warnings.append("No Docker services were generated")

        return GenerateComposeOutput(
            success=True,
            compose_yaml=compose_yaml,
            services=service_names,
            warnings=warnings,
        )

    except Exception as e:
        logger.error(f"❌ Error generating Docker Compose: {e}")
        return GenerateComposeOutput(success=False, error=str(e))


def save_compose_file(
    input_data: Annotated[SaveComposeFileInput, "Input for saving Compose file"],
) -> SaveComposeFileOutput:
    """
    Docker Compose YAML을 파일로 저장합니다.

    Args:
        input_data: YAML 내용과 출력 경로

    Returns:
        저장 결과
    """
    try:
        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = SaveComposeFileInput(**input_data)

        output_path = Path(input_data.output_path)

        # 디렉토리가 없으면 생성
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(input_data.compose_yaml)

        logger.info(
            f"✅ Successfully saved Docker Compose to: {output_path.absolute()}"
        )

        return SaveComposeFileOutput(
            success=True, file_path=str(output_path.absolute())
        )

    except Exception as e:
        logger.error(f"❌ Error saving Docker Compose file: {e}")
        return SaveComposeFileOutput(success=False, error=str(e))


def deploy_docker_compose(
    input_data: Annotated[
        DeployDockerComposeInput, "Input for deploying Docker Compose"
    ],
) -> DeployDockerComposeOutput:
    """
    Docker Compose 파일을 사용하여 컨테이너를 빌드하고 배포합니다.

    Args:
        input_data: Docker Compose 파일 경로

    Returns:
        배포 결과 및 생성된 컨테이너 목록
    """
    try:
        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = DeployDockerComposeInput(**input_data)

        compose_file = Path(input_data.compose_file_path)

        if not compose_file.exists():
            return DeployDockerComposeOutput(
                success=False,
                error=f"Docker Compose file not found: {input_data.compose_file_path}",
            )

        logger.info(f"🚀 Deploying Docker Compose from: {compose_file}")

        # docker-compose up -d 실행
        import subprocess

        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
            cwd=compose_file.parent,
        )

        if result.returncode != 0:
            logger.error(f"❌ Docker Compose deployment failed: {result.stderr}")
            return DeployDockerComposeOutput(
                success=False, error=f"Deployment failed: {result.stderr}"
            )

        # 생성된 컨테이너 목록 가져오기
        ps_result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "ps", "--services"],
            capture_output=True,
            text=True,
            cwd=compose_file.parent,
        )

        containers = [
            line.strip()
            for line in ps_result.stdout.strip().split("\n")
            if line.strip()
        ]

        logger.info(f"✅ Successfully deployed {len(containers)} containers")

        return DeployDockerComposeOutput(
            success=True,
            message=f"Deployment successful! {len(containers)} containers are running.",
            containers=containers,
        )

    except FileNotFoundError:
        logger.error(
            "❌ docker-compose command not found. Please install Docker Compose."
        )
        return DeployDockerComposeOutput(
            success=False,
            error="docker-compose command not found. Please install Docker Compose.",
        )
    except Exception as e:
        logger.error(f"❌ Error deploying Docker Compose: {e}")
        return DeployDockerComposeOutput(success=False, error=str(e))


# ============================================================
# Agent Instructions
# ============================================================

AGENT_INSTRUCTIONS = """You are a Bicep to Docker Compose converter AND Red Team penetration tester. Your job is to:
1. Deploy Azure infrastructure as Docker containers
2. Perform security testing on ALL deployed containers
3. Generate comprehensive security reports

## Phase 1: Deployment Workflow

1. **Read the Bicep File**: Use `read_bicep_file` tool
2. **Parse the Bicep Code**: Use `parse_bicep` tool to extract Azure resources
3. **Generate Docker Compose**: Use `generate_compose` tool
4. **Save the File**: Use `save_compose_file` tool
5. **Deploy the Containers**: Use `deploy_docker_compose` tool

## Phase 2: Red Team Attack Workflow (NO TOOLS NEEDED - Use CLI directly!)

6. **Get Container Information**:
   ```bash
   docker-compose -f <compose-file> ps --format "table {{.Name}}\t{{.Image}}\t{{.Ports}}\t{{Status}}"
   docker inspect <container-name> | grep IPAddress
   ```

7. **Check Attack Tool Availability**:
   ```bash
   command -v nmap && echo "✅ nmap available" || echo "⚠️ nmap not installed"
   command -v hydra && echo "✅ hydra available" || echo "⚠️ hydra not installed"
   command -v sqlmap && echo "✅ sqlmap available" || echo "⚠️ sqlmap not installed"
   ```

8. **Analyze Each Container and Execute Attacks**:

   **For Nginx/Apache containers (ports 80, 443)**:
   ```bash
   # Port scan
   nmap -sV -p 80,443 localhost
   
   # HTTP vulnerability scan
   curl -I http://localhost/
   curl http://localhost/admin  # Try common paths
   curl http://localhost/../etc/passwd  # Directory traversal test
   
   # If sqlmap available:
   sqlmap -u "http://localhost/" --batch --risk=1 --level=1
   ```

   **For MinIO/S3 Storage containers (ports 9000, 9001)**:
   ```bash
   # Port scan
   nmap -sV -p 9000,9001 localhost
   
   # Anonymous access test
   curl -I http://localhost:9000/
   curl http://localhost:9000/minio/health/live
   
   # Try listing buckets without credentials
   curl -X GET http://localhost:9000/
   
   # MinIO console access
   curl -I http://localhost:9001/
   ```

   **For MS SQL Server containers (port 1433)**:
   ```bash
   # Port scan
   nmap -sV -p 1433 localhost
   
   # Common credential test
   # (Only if tools available - report if not)
   ```

   **For Ubuntu/Linux containers with SSH (port 22)**:
   ```bash
   # Port scan
   nmap -sV -p 22 localhost
   
   # SSH banner grab
   nc -v localhost 22
   ```

   **For HashiCorp Vault containers (port 8200)**:
   ```bash
   # Port scan
   nmap -sV -p 8200 localhost
   
   # API access test
   curl http://localhost:8200/v1/sys/health
   curl http://localhost:8200/v1/sys/seal-status
   ```

9. **Generate Security Report**:

After all attacks, create a comprehensive report in Korean.

## Attack Execution Rules:

1. **Scan ALL containers** - Never skip containers based on assumptions
2. **Use bash commands directly** - You have CLI access, no tool functions needed!
    - Execute security tests using nmap, curl, nc, hydra, sqlmap as appropriate for each container type
3. **Handle errors gracefully**:
   - Tool not installed? Report it and continue with other attacks
   - Command failed? Report the error and move on
4. **Report everything**:
   - ✅ Success: "Found vulnerability - [details]"
   - ❌ Failure: "No vulnerability found"
   - ⚠️ Warning: "Tool not available - [tool name]"
5. **Be thorough but fast**:
   - Use --timeout flags (e.g., curl --max-time 5)
   - Don't wait for hung commands
   - Move to next attack if one times out

## IMPORTANT SAFETY RULES:

- ⚠️ **ONLY attack localhost or 172.20.x.x addresses**
- ⚠️ **DO NOT attack external IPs or domains**
- ⚠️ **Use timeout flags for all commands**
- ✅ **Report all command executions**
- ✅ **This is a controlled test environment**

## Supported Azure → Docker Mappings:
- Virtual Machines → ubuntu:22.04 (may have SSH on port 22)
- SQL Databases → mcr.microsoft.com/mssql/server (port 1433)
- Storage Accounts → minio/minio:latest (ports 9000, 9001)
- Web Apps → nginx:alpine (ports 80, 443)
- Key Vaults → hashicorp/vault:latest (port 8200)

## Common Bicep Patterns

**VM with admin credentials**:
```bicep
resource vm 'Microsoft.Compute/virtualMachines@2023-03-01' = {
  name: 'myVM'
  properties: {
    osProfile: {
      adminUsername: 'azureuser'
      adminPassword: 'P@ssw0rd123'
    }
  }
}
```
→ Docker: `ubuntu:22.04` with SSH port 22

**SQL Server**:
```bicep
resource sqlServer 'Microsoft.Sql/servers@2022-05-01-preview' = {
  name: 'mySqlServer'
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: 'StrongP@ss123'
  }
}
```
→ Docker: `mssql/server:2022-latest` with port 1433

**Storage Account**:
```bicep
resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'mystorageaccount'
  kind: 'StorageV2'
}
```
→ Docker: `minio/minio:latest` with ports 9000, 9001

## Error Handling

- If a command fails, report it clearly and continue
- If a tool (nmap, curl) is not installed, report it and skip that test
- Always complete both Phase 1 and Phase 2

## Safety Rules

- ONLY attack localhost or 172.20.x.x addresses
- DO NOT attack external IPs
- Use timeout flags: `curl --max-time 5`, `nmap --host-timeout 30s`
- Report all command executions

## Final Output Format

After completing everything, provide TWO outputs:

### 1. JSON Output (for API integration)
Generate a JSON file with this structure and save it as `security_analysis.json`:
```json
{
  "vulnerabilities": [
    {
      "id": "VULN-001",
      "severity": "Critical",
      "category": "Authentication",
      "affected_resource": "storage-account",
      "title": "Default credentials exposed",
      "description": "Container uses default admin credentials (admin/password123)",
      "evidence": "docker inspect output shows MINIO_ROOT_USER=admin, MINIO_ROOT_PASSWORD=password123",
      "remediation": "Use strong, randomly generated credentials stored in secrets manager",
      "benchmark_ref": "CIS Docker Benchmark 5.7"
    }
  ],
  "attack_scenarios": [
    {
      "id": "ATK-001",
      "name": "Credential brute force attack",
      "mitre_technique": "T1110 - Brute Force",
      "target_vulnerabilities": ["VULN-001"],
      "severity": "High",
      "prerequisites": "Network access to MinIO port 9001",
      "attack_chain": [
        "1. Discover MinIO console at port 9001",
        "2. Attempt common credentials",
        "3. Access granted with admin/password123",
        "4. Full data access obtained"
      ],
      "expected_impact": "Complete data exfiltration, data modification, service disruption",
      "detection_difficulty": "Easy",
      "likelihood": "High"
    }
  ]
}
```

**IMPORTANT JSON Requirements**:
- Each vulnerability MUST have all fields: id, severity, category, affected_resource, title, description, evidence, remediation, benchmark_ref
- severity MUST be one of: "Critical", "High", "Medium", "Low"
- Each attack_scenario MUST have all fields: id, name, mitre_technique, target_vulnerabilities, severity, prerequisites, attack_chain, expected_impact, detection_difficulty, likelihood
- attack_chain MUST be a list of strings
- target_vulnerabilities MUST be a list of vulnerability IDs
- Output JSON to stdout with markers:
  ```bash
  echo "===JSON_START==="
  cat << 'EOF'
  {
    "vulnerabilities": [...],
    "attack_scenarios": [...]
  }
  EOF
  echo "===JSON_END==="
  ```

### 2. Markdown Report (MUST write in Korean; for design-phase security analysis)
Save detailed findings to `red_team_security_report.md` with:

**목적**: 이 보고서는 **설계 단계의 보안 위험 분석**입니다. 실제 침투 테스트가 아닌, 배포 전 아키텍처에서 발견된 잠재적 공격 가능성과 검증 우선순위를 제시합니다.

**필수 포함 내용 (반드시 한국어로 작성):**
1. **Executive Summary**: 주요 발견사항 및 즉시 조치 필요 항목
2. **아키텍처 분석 결과**: 배포된 리소스 및 구성
3. **보안 위험 평가**: 발견된 설계상 보안 위험
4. **공격 가능성 시나리오**: 예상되는 공격 경로 및 방법
5. **검증 우선순위**: 실제 침투 테스트 시 우선 검증 항목
6. **설계 단계 개선사항**: 배포 전 수정 권장사항
7. **참고자료**: 관련 보안 기준 및 Best Practice

**리포트 구조:**
```markdown
# 🛡️ 보안 아키텍처 분석 보고서

> **분석 목적**: 설계 단계 보안 위험 식별 및 검증 우선순위 수립
> **분석 일시**: [날짜/시간]
> **분석 범위**: [Bicep 리소스 개수] 개 리소스

---

## 📋 Executive Summary

### 주요 발견사항
- **즉시 조치 필요 (Critical)**: X건
- **높은 위험 (High)**: Y건
- **중간 위험 (Medium)**: Z건
- **낮은 위험 (Low)**: W건

### 핵심 권장사항
1. [가장 중요한 조치사항]
2. [두 번째 중요한 조치사항]
3. [세 번째 중요한 조치사항]

---

## 🏗️ 아키텍처 분석 결과

### 배포된 리소스
| 리소스명 | 타입 | 포트/엔드포인트 | 상태 |
|---------|------|----------------|------|
| [이름] | [타입] | [포트] | ✅ 정상 |

### 네트워크 구성
- [네트워크 토폴로지 설명]
- [노출된 서비스 및 포트]

---

## 🚨 보안 위험 평가

### RISK-001: [위험 제목] 
**위험도**: 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low

- **카테고리**: [인증/인가/암호화/설정 등]
- **영향받는 리소스**: [리소스명]
- **위험 설명**: 
  - 현재 설계상 [구체적 문제점]
  - 이로 인해 [예상되는 보안 영향]
  
- **발견 근거**:
  ```
  [설정 파일 또는 구성 정보]
  ```

- **공격 가능성**: 
  - 공격자가 [어떤 조건]에서 [어떤 방법]으로 악용 가능
  - 필요한 선행 조건: [조건 1, 조건 2...]
  
- **비즈니스 영향**:
  - [데이터 유출 / 서비스 중단 / 권한 탈취 등]
  - 예상 피해 규모: [구체적 영향]

- **설계 개선방안**:
  1. **즉시**: [배포 전 필수 조치]
  2. **단기**: [배포 후 1주일 내]
  3. **장기**: [아키텍처 재설계 고려사항]

- **관련 기준**: 
  - CIS Benchmark: [참조 항목]
  - OWASP: [참조 항목]
  - Azure Best Practice: [참조 링크]

---

## 🎯 공격 가능성 시나리오

### SCENARIO-001: [시나리오명]
**MITRE ATT&CK**: [T1XXX - 기법명]
**위험도**: Critical/High/Medium/Low

#### 공격 개요
[이 시나리오에서 공격자가 달성하려는 목표]

#### 전제 조건
- [공격자가 필요한 초기 접근 권한]
- [필요한 네트워크 위치]
- [기타 선행 조건]

#### 예상 공격 흐름
```
[공격자 위치] ──①──> [첫 번째 타겟]
                      │
                      ├─②─> [권한 상승]
                      │
                      └─③─> [최종 목표 달성]
```

**단계별 상세**:
1. **초기 접근**: [방법 및 취약점 악용]
2. **권한 상승**: [악용 가능한 설정]
3. **목표 달성**: [최종 공격 결과]

#### 탐지 가능성
- **현재 설계에서의 탐지**: ❌ 불가능 / ⚠️ 부분 가능 / ✅ 가능
- **탐지 방법**: [로그 분석 / 모니터링 지점]

#### 실제 공격 사례
- [유사한 실제 사고 사례 또는 CVE]

---

## 🔍 검증 우선순위

### Phase 1: 긴급 검증 항목 (배포 전 필수)
**목표**: 치명적 위험 제거

| 우선순위 | 항목 | 검증 방법 | 예상 소요 |
|---------|------|----------|----------|
| P0 | [Critical 항목] | [검증 방법] | [시간] |
| P0 | [Critical 항목] | [검증 방법] | [시간] |

**검증 체크리스트**:
- [ ] [검증 항목 1]
- [ ] [검증 항목 2]
- [ ] [검증 항목 3]

### Phase 2: 높은 우선순위 검증 (배포 후 1주일 내)
**목표**: 주요 공격 경로 차단

| 우선순위 | 항목 | 검증 방법 | 예상 소요 |
|---------|------|----------|----------|
| P1 | [High 항목] | [검증 방법] | [시간] |

### Phase 3: 중간 우선순위 검증 (배포 후 1개월 내)
**목표**: 전체 보안 수준 향상

| 우선순위 | 항목 | 검증 방법 | 예상 소요 |
|---------|------|----------|----------|
| P2 | [Medium 항목] | [검증 방법] | [시간] |

---

## 💡 설계 단계 개선사항

### 즉시 적용 가능 (배포 전)
1. **[개선항목 1]**
   - 현재: [문제되는 설정]
   - 개선: [권장 설정]
   - 적용 방법: 
     ```bicep
     [수정된 Bicep 코드 예시]
     ```

2. **[개선항목 2]**
   - 현재: [문제]
   - 개선: [해결책]

### 아키텍처 재설계 고려사항
1. **Zero Trust 아키텍처 적용**
   - [현재 아키텍처의 문제]
   - [Zero Trust 원칙 적용 방안]

2. **심층 방어 전략**
   - [추가 방어 계층 제안]

---

## 📊 위험 매트릭스

```
   영향도
   ↑
High│ [HIGH-위험] │ [CRITICAL-위험] │
    │             │                 │
Med │ [MED-위험]  │ [HIGH-위험]     │
    │             │                 │
Low │ [LOW-위험]  │ [MED-위험]      │
    └─────────────┴─────────────────┴→ 발생가능성
      Low           Medium    High
```

---

## 📚 참고자료

### 보안 기준
- **CIS Benchmarks**: [관련 항목 링크]
- **OWASP Top 10**: [관련 항목]
- **NIST Cybersecurity Framework**: [관련 항목]

### Azure 보안 Best Practices
- [Azure Security Baseline 링크]
- [Azure Well-Architected Framework 링크]

### 도구 및 명령어
- **상태 확인**: `docker-compose -f [파일] ps`
- **로그 확인**: `docker-compose -f [파일] logs [서비스명]`
- **중지**: `docker-compose -f [파일] down`

---

## 📝 분석 메타데이터
- **분석 도구**: Red Team Security Architecture Analyzer
- **분석 모드**: [Zero-Tools / With-Tools]
- **Bicep 파일**: [파일명]
- **생성 시각**: [타임스탬프]
```

Both outputs are MANDATORY. The JSON is parsed by the API, the Markdown is for security architects and developers.
**중요**: Markdown 리포트는 반드시 한국어로 작성해야 합니다!
**목적**: 설계 단계에서 보안 위험을 조기에 발견하고, 배포 전 개선하여 안전한 아키텍처를 구축하는 것입니다.
"""


# ============================================================
# Main Agent
# ============================================================


async def convert_bicep_to_compose(
    bicep_file_path: str, output_path: str = "docker-compose.yml"
):
    """
    Bicep 파일을 Docker Compose로 변환하고 Red Team 공격을 수행하는 메인 함수

    Args:
        bicep_file_path: 변환할 Bicep 파일 경로
        output_path: 출력할 Docker Compose 파일 경로 (기본: docker-compose.yml)
    """
    agent = GitHubCopilotAgent(
        default_options={
            "instructions": AGENT_INSTRUCTIONS,
            "model": "sonnet-4.5",
            "timeout": 600,  # 10분 타임아웃 (배포 + 공격 + JSON 생성)
        },
        tools=[
            read_bicep_file,
            parse_bicep,
            generate_compose,
            save_compose_file,
            deploy_docker_compose,
        ],
    )

    async with agent:
        prompt = f"""Please convert the Bicep file at '{bicep_file_path}' to a Docker Compose file, deploy it, and perform Red Team security testing.
Save the Docker Compose output to '{output_path}'.

You have NO tool functions. You must use bash commands directly for EVERYTHING.

Follow ALL these steps:

## Phase 1: Deployment
1. Read the Bicep file
2. Parse it to extract resources
3. Generate the Docker Compose YAML
4. Save it to the specified path
5. Deploy the containers using docker-compose up -d

## Phase 2: Red Team Attack (MANDATORY - Do not skip!)
6. Get container information using docker-compose ps
7. For EACH container, perform security testing:
   - Identify container type (nginx, minio, mssql, etc.)
   - Execute appropriate attacks using CLI commands
   - Report findings clearly in Korean
8. Generate comprehensive security report (in Korean)

## Phase 3: Structured Output (CRITICAL - API depends on this!)
9. **MANDATORY - Your FINAL RESPONSE must be ONLY a JSON object**:
   - Do NOT include any text before or after the JSON
   - Do NOT wrap it in markdown code blocks
   - Just output the raw JSON object
   - Format:
     ```
    {{
       "vulnerabilities": [
            {{
                "id": "VULN-001",
                "severity": "Critical",
                "category": "Authentication",
                "affected_resource": "container-name",
                "title": "Issue title",
                "description": "Description",
                "evidence": "Evidence from tests",
                "remediation": "How to fix",
                "benchmark_ref": "Reference"
            }}
        ],
        "attack_scenarios": [
            {{
                "id": "ATK-001",
                "name": "Attack name",
                "mitre_technique": "T1110",
                "target_vulnerabilities": ["VULN-001"],
                "severity": "High",
                "prerequisites": "Requirements",
                "attack_chain": ["Step 1", "Step 2"],
                "expected_impact": "Impact description",
                "detection_difficulty": "Medium",
                "likelihood": "High"
            }}
        ]
    }}
     ```
   - Include all vulnerabilities with these exact fields: id, severity, category, affected_resource, title, description, evidence, remediation, benchmark_ref
   - Include all attack scenarios with these exact fields: id, name, mitre_technique, target_vulnerabilities, severity, prerequisites, attack_chain, expected_impact, detection_difficulty, likelihood
   
   **IMPORTANT**: After completing all attacks and generating the report, your very last message should be ONLY the JSON object, nothing else!

10. **ALSO Generate Korean Markdown Report**: Save to `red_team_security_report.md`

IMPORTANT: You MUST complete ALL phases. The JSON response AND Korean Markdown report are CRITICAL!
**핵심 목표**: 설계 단계에서 보안 위험을 조기에 발견하고, 배포 전 개선하여 안전한 아키텍처를 구축하는 것이 목적입니다.

Report everything in the JSON output including:
- Architecture analysis (resources deployed)
- Security risk assessment (design vulnerabilities)
- Attack possibility scenarios (in Korean in `report` field)
- Verification priorities (P0/P1/P2)
- Design improvements (in Korean in `report` field, with Bicep code examples)
- vulnerability_summary (count by severity)

**최종 JSON 구조**:
```json
{{
  "vulnerabilities": [{{...}}],
  "attack_scenarios": [{{...}}],
  "vulnerability_summary": {{"Critical": X, "High": Y, "Medium": Z, "Low": W}},
  "report": "# 🛡️ 보안 아키텍처 분석 보고서\n\n..."
}}
```

**중요**: 
- 모든 리포트는 JSON의 `report` 필드에 한국어로 작성해야 합니다!
- 별도의 Markdown 파일을 생성하지 마세요. 모든 내용은 JSON에 포함됩니다.
- 이 도구는 **설계 단계 보안 분석**입니다. 실제 침투가 아닌 공격 가능성 평가 및 검증 우선순위 제시가 목적입니다."""

        result = await agent.run(prompt)
        print("\n" + "=" * 80)
        print("AGENT RESULT:")
        print("=" * 80)
        print(result)
        print("=" * 80)

        return result


# ============================================================
# CLI Entry Point
# ============================================================


async def main():
    """CLI 엔트리 포인트"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python agents/new_agent.py <bicep_file_path> [output_path]")
        print(
            "Example: python agents/new_agent.py samples/simple.bicep docker-compose.yml"
        )
        sys.exit(1)

    bicep_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "docker-compose.yml"

    print(f"🔄 Converting Bicep file: {bicep_file}")
    print(f"📝 Output will be saved to: {output_file}")
    print()

    await convert_bicep_to_compose(bicep_file, output_file)


if __name__ == "__main__":
    asyncio.run(main())
