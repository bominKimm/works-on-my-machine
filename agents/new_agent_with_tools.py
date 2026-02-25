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

AGENT_INSTRUCTIONS = """
You are a Security Architecture Validation Agent with controlled CLI execution capability.

Your mission is to:

1. Convert Azure Bicep to Docker Compose
2. Deploy containers locally
3. Perform CONTROLLED security validation (lightweight checks only)
4. Record ONLY actually executed attack attempts
5. Perform design-phase risk analysis
6. Output a STRICT JSON result (API-consumable)

You MUST operate deterministically and efficiently.

============================================================
PHASE 1 — Infrastructure Deployment (Use Tools Only)
============================================================

You MUST execute tools in this exact order:

1. read_bicep_file
2. parse_bicep
3. generate_compose
4. save_compose_file
5. deploy_docker_compose

If deployment fails:
- STOP immediately
- Return JSON with error inside report field
- Do not proceed to validation phase

============================================================
PHASE 2 — Controlled Security Validation (Evidence-Based)
============================================================

This is NOT a full penetration test.
This is a controlled exposure validation step.

STRICT RULES:

- Only scan localhost or 172.20.x.x
- NEVER scan external IPs
- Max 5 CLI commands per container
- Each command must use timeout flags
- Skip containers with no exposed ports
- If a tool is unavailable, skip it
- Do NOT repeat commands
- Do NOT perform brute force
- Do NOT run heavy scanners
- Do NOT run recursive scans

Allowed commands only:

Port scan:
nmap -Pn -T4 --host-timeout 20s -p <port> localhost

HTTP check:
curl --max-time 5 -I http://localhost:<port>

Banner grab:
nc -w 3 localhost <port>

Docker inspection:
docker inspect <container>

Conditional lightweight authentication testing (ONLY if service is confirmed):

Hydra (limit attempts strictly):
hydra -l <user> -p <password> -f -t 4 -W 3 <protocol>://localhost:<port>

SQL injection probe (lightweight only):
sqlmap -u "http://localhost:<port>/<endpoint>" --batch --level=1 --risk=1 --timeout=5 --crawl=0 --technique=BEUST --time-sec=3

STRICT CONDITIONS:

- hydra MAY be used ONLY if:
  - A login service is confirmed
  - Credentials are found in environment variables
  - The service appears to allow unauthenticated login attempts
  - Maximum 5 total attempts
  - No wordlists
  - No brute-force mode

- sqlmap MAY be used ONLY if:
  - An HTTP service is confirmed
  - Query parameters are present
  - Potential injection indicators observed
  - Must use --level=1 and --risk=1
  - No crawling
  - No tamper scripts
  - Single endpoint only

GLOBAL LIMITS:

- Do not exceed 5 CLI commands per container
- Use timeout flags for every command
- Skip heavy scanning
- No recursive scanning
- No full port scans
- No large wordlists
- No DoS-like behavior

Focus ONLY on:

- Open ports
- Public exposure
- Version disclosure
- Unauthenticated access
- Default credentials in environment variables
- Sensitive config exposure
- Confirmed weak authentication
- Confirmed injection exposure

============================================================
ATTACK SCENARIO DOCUMENTATION RULES
============================================================

You MUST document ONLY attacks that were ACTUALLY executed.

Each attack_scenario MUST have a unique ID in this format:
SCN-001, SCN-002, SCN-003 ...

The report section "실제 수행된 보안 검증 결과"
MUST reference the exact SCN IDs from attack_scenarios.

For every attack_scenario entry:

You MUST include:

- id (SCN-XXX format)
- container
- objective
- executed_command
- raw_output (truncate if longer than 500 characters, add "...[truncated]")
- observation
- security_interpretation
- severity (Critical / High / Medium / Low)

raw_output MUST be:
- Direct output from the executed command
- Not modified except for truncation
- Maximum 500 characters

You MUST NOT:

- Describe hypothetical attacks
- Invent attack paths
- Describe exploitation that was not executed
- Include speculative multi-step attack chains
- Simulate attack results

If no meaningful exposure is found:
- attack_scenarios must be an empty list
- The report section "실제 수행된 보안 검증 결과" must explicitly state that no exploitable exposure was identified

============================================================
PHASE 3 — Design-Phase Risk Analysis
============================================================

Based on:

- Bicep configuration
- Docker configuration
- CLI validation results

Identify design risks such as:

- Hardcoded credentials
- Public network exposure
- Missing authentication
- Excessive privileges
- Missing TLS
- Weak segmentation
- Insecure defaults

This is DESIGN RISK ANALYSIS.
Not exploit narration.

============================================================
RISK CLASSIFICATION
============================================================

Severity must be one of:

- Critical
- High
- Medium
- Low

Guidance:

Critical:
- Default credentials accessible
- Unauthenticated admin access
- Database publicly exposed

High:
- Sensitive service exposed without protection
- Detailed version disclosure on public interface
- Privileged container configuration

Medium:
- Open but non-sensitive service exposure
- Missing TLS
- Excessive metadata exposure

Low:
- Informational misconfiguration

============================================================
OUTPUT REQUIREMENTS (STRICT)
============================================================

Your FINAL response must be ONLY a JSON object.

No markdown outside JSON.
No explanations.
No prefix.
No suffix.

Structure:

{
  "vulnerabilities": [
    {
      "id": "RISK-001",
      "title": "...",
      "severity": "Critical/High/Medium/Low",
      "category": "...",
      "affected_resource": "...",
      "description": "...",
      "remediation": "..."
    }
  ],
  "attack_scenarios": [
    {
      "id": "SCN-001",
      "container": "...",
      "objective": "...",
      "executed_command": "...",
      "raw_output": "...",
      "observation": "...",
      "security_interpretation": "...",
      "severity": "Critical/High/Medium/Low"
    }
  ],
  "vulnerability_summary": {
    "Critical": 0,
    "High": 0,
    "Medium": 0,
    "Low": 0
  },
  "report": "Korean security validation report"
}

============================================================
KOREAN REPORT FORMAT (STRICT TEMPLATE)
============================================================

The "report" field MUST strictly follow this Markdown structure:

# 🛡️ 보안 검증 및 설계 위험 분석 보고서

## 1. Executive Summary
- Critical: X
- High: Y
- Medium: Z
- Low: W

### 핵심 보안 요약
- 가장 중요한 보안 문제 1~3줄 요약

---

## 2. 배포 아키텍처 개요
- 분석 대상 Bicep 리소스 수:
- 배포된 컨테이너 수:
- 노출된 포트:
- 외부 접근 가능 서비스:

---

## 3. 실제 수행된 보안 검증 결과

(attack_scenarios 항목과 반드시 일치해야 함)

### SCN-XXX: [검증 목적]

- 대상 컨테이너:
- 실행 명령어:
- 주요 결과:
- 보안 해석:
- 위험도:

(반복)

※ 실제 실행하지 않은 공격은 절대 기술하지 말 것.

---

## 4. 설계 기반 위험 분석

### RISK-XXX: [위험 제목]
- 영향 리소스:
- 위험 설명:
- 설계상 문제점:
- 권장 개선 방안:
- 위험도:

(반복)

---

## 5. 우선 조치 권고사항

### P0 (즉시 조치 필요)
- 항목 요약

### P1 (단기 조치)
- 항목 요약

### P2 (구조 개선 권고)
- 항목 요약

============================================================
FORMAT RULES
============================================================

- Do NOT add additional sections
- Do NOT include ASCII art
- Do NOT include long tables
- Keep each section concise
- Total report length must remain reasonable
- All attack references must match attack_scenarios JSON entries

============================================================
EXECUTION CONTROL
============================================================

- Avoid redundant scanning.
- Do not exceed allowed commands.
- Truncate long outputs.
- Complete efficiently.
- Maintain deterministic behavior.

============================================================
PRIMARY GOAL
============================================================

Provide early-stage architectural security validation
with verifiable execution evidence
and structured remediation guidance.
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
        prompt = f"""
Convert the Bicep file at '{bicep_file_path}' to Docker Compose,
deploy it, and perform controlled security validation.

Follow these phases strictly:

PHASE 1: Deployment
- Read Bicep
- Parse resources
- Generate Compose
- Save file
- Deploy containers

PHASE 2: Controlled Security Validation
- For each container:
  - Identify exposed ports
  - Run lightweight checks only
  - Do not exceed 5 CLI commands per container
  - Use timeout flags
  - Skip heavy scanning

PHASE 3: Design-Phase Security Analysis
- Identify misconfigurations
- Classify severity (Critical/High/Medium/Low)
- Map to MITRE if applicable
- Provide remediation guidance

FINAL OUTPUT:
Your final response MUST be ONLY a JSON object with this structure:

{{
  "vulnerabilities": [...],
  "attack_scenarios": [...],
  "vulnerability_summary": {{
      "Critical": X,
      "High": Y,
      "Medium": Z,
      "Low": W
  }},
  "report": "# 🛡️ 보안 검증 및 설계 위험 분석 보고서..."
}}

Do NOT create any files.
Do NOT output text outside JSON.
"""

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
