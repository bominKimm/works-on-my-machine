"""
Zero-Tools Bicep to Docker Compose Converter + Red Team Attack Agent

이 Agent는 도구 함수 없이(tools=[]) 모든 작업을 수행합니다.
프롬프트에 모든 정보를 제공하여 Agent가 직접 bash 명령어로 작업합니다.
"""

import asyncio
import logging
from agent_framework.github import GitHubCopilotAgent

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# ============================================================
# Agent Instructions (모든 정보 포함)
# ============================================================

AGENT_INSTRUCTIONS = """You are a Bicep to Docker Compose converter AND Red Team penetration tester. 
Your job is to convert Azure Bicep files to Docker Compose format, deploy containers, and perform security testing.

**IMPORTANT**: You have NO tool functions. You must use bash commands directly for EVERYTHING.

## Phase 1: Bicep to Docker Compose Conversion & Deployment

### Step 1: Read Bicep File
Use `cat` command:
```bash
cat <bicep_file_path>
```

### Step 2: Understand Bicep and Extract Resources
Analyze the Bicep code and identify Azure resources. Common patterns:

**Bicep Resource Syntax**:
```bicep
resource <name> '<type>@<version>' = {
  name: '<resource_name>'
  location: '<location>'
  properties: {
    ...
  }
}
```

**Common Azure Resource Types**:
- `Microsoft.Compute/virtualMachines` - Virtual Machine
- `Microsoft.Sql/servers` or `servers/databases` - SQL Server/Database
- `Microsoft.Storage/storageAccounts` - Storage Account
- `Microsoft.Web/sites` or `serverfarms` - Web App
- `Microsoft.KeyVault/vaults` - Key Vault
- `Microsoft.Network/networkSecurityGroups` - Network Security Group
- `Microsoft.Network/virtualNetworks` - Virtual Network

### Step 3: Map Azure Resources to Docker Services

**Mapping Table**:
| Azure Resource | Docker Image | Environment Variables | Ports |
|---------------|--------------|----------------------|-------|
| VM (virtualMachines) | ubuntu:22.04 | - | 22, 80, 443, 3389 |
| SQL Server | mcr.microsoft.com/mssql/server:2022-latest | ACCEPT_EULA=Y<br>MSSQL_SA_PASSWORD=YourStrong!Passw0rd<br>MSSQL_PID=Developer | 1433 |
| Storage Account | minio/minio:latest | MINIO_ROOT_USER=admin<br>MINIO_ROOT_PASSWORD=password123 | 9000, 9001 |
| Web App | nginx:alpine | - | 80, 443 |
| Key Vault | hashicorp/vault:latest | VAULT_DEV_ROOT_TOKEN_ID=root<br>VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 | 8200 |

### Step 4: Generate Docker Compose YAML

**Template**:
```yaml
version: '3.8'
services:
  <service_name>:
    image: <docker_image>
    container_name: <container_name>
    networks:
      - attack_network
    restart: unless-stopped
    environment:
      KEY: value
    ports:
      - "<host_port>:<container_port>"
    command: <optional_command>

networks:
  attack_network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

**Service Naming**: Use format `<type>_<resource_name>` (e.g., `vm_webVM`, `storage_storageAccount`)

**Port Mapping**: 
- First service: use original ports (e.g., 80:80)
- Duplicate services: increment host port (e.g., 1433:1433, 2433:1433, 3433:1433)

### Step 5: Save Docker Compose File
```bash
cat > <output_file> << 'EOF'
<yaml_content>
EOF
```

### Step 6: Deploy Containers
```bash
docker-compose -f <output_file> up -d
```

### Step 7: Verify Deployment
```bash
docker-compose -f <output_file> ps
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

## Phase 2: Red Team Security Testing

### Step 8: Get Container Information
```bash
docker-compose -f <output_file> ps --format "table {{.Name}}\t{{.Image}}\t{{.Ports}}"
```

### Step 9: Check Attack Tool Availability:
    ```bash
   command -v nmap && echo "✅ nmap available" || echo "⚠️ nmap not installed"
   command -v hydra && echo "✅ hydra available" || echo "⚠️ hydra not installed"
   command -v sqlmap && echo "✅ sqlmap available" || echo "⚠️ sqlmap not installed"
   ```

### Step 10: Analyze Each Container and Execute Attacks

**For Nginx/Apache (nginx:alpine, httpd)**:
```bash
# Port scan
nmap -sV -p 80,443 localhost

# HTTP vulnerability test
curl -I http://localhost/
curl http://localhost/admin
curl http://localhost/../etc/passwd

# Check for directory listing
curl http://localhost/ | grep "Index of"
```

**For MinIO/S3 Storage (minio/minio)**:
```bash
# Port scan
nmap -sV -p 9000,9001 localhost

# Anonymous access test
curl -I http://localhost:9000/
curl http://localhost:9000/minio/health/live

# Console access
curl -I http://localhost:9001/

# Try listing buckets (should fail without auth)
curl -X GET http://localhost:9000/
```

**For MS SQL Server (mssql/server)**:
```bash
# Port scan
nmap -sV -p 1433,2433,3433 localhost

# Check if server responds
nc -zv localhost 1433

# Version detection
nmap -sV -p 1433 localhost
```

**For Ubuntu/VM (ubuntu)**:
```bash
# Port scan
nmap -sV -p 22,80,443,3389 localhost

# SSH banner grab
nc -v localhost 22

# Check if SSH is accessible
ssh -o ConnectTimeout=5 root@localhost 2>&1 | head -5
```

**For HashiCorp Vault (vault)**:
```bash
# Port scan
nmap -sV -p 8200 localhost

# Health check
curl http://localhost:8200/v1/sys/health

# Seal status
curl http://localhost:8200/v1/sys/seal-status

# Try accessing with dev token (if exposed)
curl -H "X-Vault-Token: root" http://localhost:8200/v1/sys/health
```

### Step 11: Generate Security Report

After all attacks, create a comprehensive report in Korean.


## Execution Rules

1. **Read Bicep File**: Use `cat` to read the file
2. **Parse Manually**: Read the Bicep code and identify resources yourself
3. **Map to Docker**: Use the mapping table above
4. **Generate YAML**: Write docker-compose.yml using heredoc (`cat > file << 'EOF'`)
5. **Deploy**: Run `docker-compose up -d`
6. **Attack**: Execute security tests using nmap, curl, nc, hydra, sqlmap as appropriate for each container type
7. **Report**: Create markdown report in Korean

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
- vulnerability_summary MUST be an object with severity counts: {{"Critical": 0, "High": 0, "Medium": 0, "Low": 0}}
- report MUST be a string containing the complete Korean markdown report

**Output the final JSON with this structure**:
```json
{{
  "vulnerabilities": [...],
  "attack_scenarios": [...],
  "vulnerability_summary": {{"Critical": X, "High": Y, "Medium": Z, "Low": W}},
  "report": "# 🛡️ 보안 아키텍처 분석 보고서\n\n> **분석 목적**: ...\n\n## 📋 Executive Summary\n..."
}}
```

**How to output**:
```bash
echo "===JSON_START==="
cat << 'EOF'
{{
  "vulnerabilities": [...],
  "attack_scenarios": [...],
  "vulnerability_summary": {{"Critical": 2, "High": 5, "Medium": 3, "Low": 1}},
  "report": "# 전체 한국어 마크다운 리포트를 여기에..."
}}
EOF
echo "===JSON_END==="
```

### 2. Report Content (for the `report` field in JSON)
**MUST write in Korean; for design-phase security analysis**

The `report` field must contain a complete Korean markdown report with:

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

Both outputs are MANDATORY. The JSON with embedded report is parsed by the API, the report field is displayed to users.
**중요**: 
- Markdown 리포트는 JSON의 `report` 필드에 포함되어야 합니다!
- 별도의 파일을 생성하지 마세요.
- 이 도구는 **설계 단계 보안 분석**입니다. 실제 침투가 아닌 공격 가능성 평가 및 검증 우선순위 제시가 목적입니다.
"""


# ============================================================
# Main Agent
# ============================================================


async def convert_and_attack(
    bicep_file_path: str, output_path: str = "docker-compose.yml"
):
    """
    Zero-tools Agent: Bicep → Docker Compose → Deploy → Attack

    Args:
        bicep_file_path: Bicep 파일 경로
        output_path: 출력 Docker Compose 파일 경로
    """
    agent = GitHubCopilotAgent(
        default_options={
            "instructions": AGENT_INSTRUCTIONS,
            "model": "sonnet-4.5",
            "timeout": 600,  # 10분 (배포 + 공격에 충분한 시간)
        },
        tools=[],  # NO TOOLS! Agent does everything via bash
    )

    async with agent:
        prompt = f"""Please convert the Bicep file at '{bicep_file_path}' to Docker Compose, deploy it, and perform Red Team security testing.
Save the Docker Compose output to '{output_path}'.

You have NO tool functions. You must use bash commands directly for EVERYTHING.

Follow ALL these tasks:

## Phase 1: Conversion & Deployment
1. Read the Bicep file using `cat`
2. Analyze the Bicep code and identify all Azure resources
3. Map each Azure resource to the appropriate Docker image using the mapping table
4. Generate a valid docker-compose.yml file using `cat > {output_path} << 'EOF'`
5. Deploy containers using `docker-compose -f {output_path} up -d`
6. Verify deployment using `docker-compose ps` and `docker ps`

## Phase 2: Red Team Attack
7. Get container information
8. For EACH container, perform appropriate security tests based on its image type
9. Document all findings

## CRITICAL: Structured Output
10. **MANDATORY**: Create security_analysis.json using this EXACT bash command:
```bash
cat > security_analysis.json << 'EOF'
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
EOF
```

11. Generate red_team_security_report.md as usual

REMEMBER: You must do EVERYTHING using bash commands. No tool functions are available.
The security_analysis.json file is CRITICAL - the API depends on it!

Start now and complete both phases!"""

        result = await agent.run(prompt)
        print("\n" + "=" * 80)
        print("ZERO-TOOLS AGENT RESULT:")
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
        print(
            "Usage: python agents/new_agent_notool.py <bicep_file_path> [output_path]"
        )
        print(
            "Example: python agents/new_agent_notool.py samples/simple.bicep docker-compose.yml"
        )
        sys.exit(1)

    bicep_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "docker-compose-notool.yml"

    print(f"🔄 Zero-Tools Agent Test")
    print(f"📁 Bicep file: {bicep_file}")
    print(f"📝 Output: {output_file}")
    print(f"⚠️  NO TOOL FUNCTIONS - Agent will use bash commands directly")
    print()

    await convert_and_attack(bicep_file, output_file)


if __name__ == "__main__":
    asyncio.run(main())
