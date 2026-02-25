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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from agents.agent import BicepParser, ResourceMapper, DockerComposer, NetworkConfig, BicepResource

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


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
    output_path: str = Field(default="docker-compose.yml", description="Output file path")


class SaveComposeFileOutput(BaseModel):
    """Docker Compose 파일 저장 도구 출력"""
    success: bool
    file_path: str | None = None
    error: str | None = None


class DeployDockerComposeInput(BaseModel):
    """Docker Compose 배포 도구 입력"""
    compose_file_path: str = Field(description="Path to the docker-compose.yml file to deploy")


class DeployDockerComposeOutput(BaseModel):
    """Docker Compose 배포 도구 출력"""
    success: bool
    message: str | None = None
    containers: List[str] = []
    error: str | None = None


# ============================================================
# Tool Functions
# ============================================================


def read_bicep_file(input_data: Annotated[ReadBicepFileInput, "Input for reading Bicep file"]) -> ReadBicepFileOutput:
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
                success=False,
                error=f"File not found: {input_data.file_path}"
            )
        
        with open(file_path, 'r', encoding='utf-8') as f:
            bicep_code = f.read()
        
        logger.info(f"✅ Successfully read Bicep file: {input_data.file_path}")
        return ReadBicepFileOutput(
            success=True,
            bicep_code=bicep_code
        )
    
    except Exception as e:
        logger.error(f"❌ Error reading Bicep file: {e}")
        return ReadBicepFileOutput(
            success=False,
            error=str(e)
        )


def parse_bicep(input_data: Annotated[ParseBicepInput, "Input for parsing Bicep code"]) -> ParseBicepOutput:
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
                "location": r.location
            }
            for r in resources
        ]
        
        network_config_dict = {
            "subnets": network_config.subnets,
            "security_rules": network_config.security_rules,
            "public_ips": network_config.public_ips
        }
        
        logger.info(f"✅ Successfully parsed {len(resources)} resources")
        
        warnings = []
        if not resources:
            warnings.append("No Azure resources found in Bicep code")
        
        return ParseBicepOutput(
            success=True,
            resources=resources_dict,
            network_config=network_config_dict,
            warnings=warnings
        )
    
    except Exception as e:
        logger.error(f"❌ Error parsing Bicep code: {e}")
        return ParseBicepOutput(
            success=False,
            error=str(e)
        )


def generate_compose(input_data: Annotated[GenerateComposeInput, "Input for generating Docker Compose"]) -> GenerateComposeOutput:
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
                location=r.get("location", "")
            )
            for r in input_data.resources
        ]
        
        network_config = NetworkConfig(
            subnets=input_data.network_config.get("subnets", []),
            security_rules=input_data.network_config.get("security_rules", []),
            public_ips=input_data.network_config.get("public_ips", [])
        )
        
        # ResourceMapper로 Docker 서비스 매핑
        mapper = ResourceMapper(resources, network_config)
        service_mapping = mapper.map_to_docker()
        
        # DockerComposer로 YAML 생성
        composer = DockerComposer(service_mapping)
        compose_yaml = composer.generate_compose_file()
        
        service_names = list(service_mapping.keys())
        
        logger.info(f"✅ Successfully generated Docker Compose with {len(service_names)} services")
        
        warnings = []
        if len(service_names) == 0:
            warnings.append("No Docker services were generated")
        
        return GenerateComposeOutput(
            success=True,
            compose_yaml=compose_yaml,
            services=service_names,
            warnings=warnings
        )
    
    except Exception as e:
        logger.error(f"❌ Error generating Docker Compose: {e}")
        return GenerateComposeOutput(
            success=False,
            error=str(e)
        )


def save_compose_file(input_data: Annotated[SaveComposeFileInput, "Input for saving Compose file"]) -> SaveComposeFileOutput:
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
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(input_data.compose_yaml)
        
        logger.info(f"✅ Successfully saved Docker Compose to: {output_path.absolute()}")
        
        return SaveComposeFileOutput(
            success=True,
            file_path=str(output_path.absolute())
        )
    
    except Exception as e:
        logger.error(f"❌ Error saving Docker Compose file: {e}")
        return SaveComposeFileOutput(
            success=False,
            error=str(e)
        )


def deploy_docker_compose(input_data: Annotated[DeployDockerComposeInput, "Input for deploying Docker Compose"]) -> DeployDockerComposeOutput:
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
                error=f"Docker Compose file not found: {input_data.compose_file_path}"
            )
        
        logger.info(f"🚀 Deploying Docker Compose from: {compose_file}")
        
        # docker-compose up -d 실행
        import subprocess
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
            cwd=compose_file.parent
        )
        
        if result.returncode != 0:
            logger.error(f"❌ Docker Compose deployment failed: {result.stderr}")
            return DeployDockerComposeOutput(
                success=False,
                error=f"Deployment failed: {result.stderr}"
            )
        
        # 생성된 컨테이너 목록 가져오기
        ps_result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "ps", "--services"],
            capture_output=True,
            text=True,
            cwd=compose_file.parent
        )
        
        containers = [line.strip() for line in ps_result.stdout.strip().split('\n') if line.strip()]
        
        logger.info(f"✅ Successfully deployed {len(containers)} containers")
        
        return DeployDockerComposeOutput(
            success=True,
            message=f"Deployment successful! {len(containers)} containers are running.",
            containers=containers
        )
    
    except FileNotFoundError:
        logger.error("❌ docker-compose command not found. Please install Docker Compose.")
        return DeployDockerComposeOutput(
            success=False,
            error="docker-compose command not found. Please install Docker Compose."
        )
    except Exception as e:
        logger.error(f"❌ Error deploying Docker Compose: {e}")
        return DeployDockerComposeOutput(
            success=False,
            error=str(e)
        )


# ============================================================
# Agent Instructions
# ============================================================

AGENT_INSTRUCTIONS = """You are a Bicep to Docker Compose converter agent. Your job is to read Azure Bicep infrastructure-as-code files, generate valid docker-compose.yml files, and deploy them using docker-compose.

## Your Workflow:

1. **Read the Bicep File**: Use `read_bicep_file` with the provided file path
2. **Parse the Bicep Code**: Use `parse_bicep` to extract Azure resources and network configuration
3. **Generate Docker Compose**: Use `generate_compose` to create the docker-compose.yml content
4. **Save the File**: Use `save_compose_file` to write the YAML to disk
5. **Deploy the Containers**: Use `deploy_docker_compose` to run `docker-compose up -d` and start all containers

## Supported Azure Resources:
- Virtual Machines → ubuntu:22.04
- SQL Databases → mcr.microsoft.com/mssql/server:2022-latest
- Storage Accounts → minio/minio:latest
- Web Apps → nginx:alpine
- Key Vaults → hashicorp/vault:latest

## Important:
- Report progress at each step
- Handle errors gracefully and provide clear messages
- After successful conversion, save the file AND deploy it
- After deployment, list all running containers
- Warn about default credentials (remind users to change for production)
- Provide instructions on how to check container status: `docker-compose ps`
- Provide instructions on how to stop containers: `docker-compose down`
"""


# ============================================================
# Main Agent
# ============================================================


async def convert_bicep_to_compose(bicep_file_path: str, output_path: str = "docker-compose.yml"):
    """
    Bicep 파일을 Docker Compose로 변환하는 메인 함수
    
    Args:
        bicep_file_path: 변환할 Bicep 파일 경로
        output_path: 출력할 Docker Compose 파일 경로 (기본: docker-compose.yml)
    """
    agent = GitHubCopilotAgent(
        default_options={
            "instructions": AGENT_INSTRUCTIONS,
            "model": "sonnet-4.5",
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
        prompt = f"""Please convert the Bicep file at '{bicep_file_path}' to a Docker Compose file and deploy it.
Save the output to '{output_path}'.

Follow these steps:
1. Read the Bicep file
2. Parse it to extract resources
3. Generate the Docker Compose YAML
4. Save it to the specified path
5. Deploy the containers using docker-compose up -d

Report the results clearly, including:
- List of services created
- Deployment status
- List of running containers
- Any warnings or security considerations
- Instructions on how to check status (docker-compose ps) and stop containers (docker-compose down)"""

        result = await agent.run(prompt)
        print("\n" + "="*80)
        print("AGENT RESULT:")
        print("="*80)
        print(result)
        print("="*80)
        
        return result


# ============================================================
# CLI Entry Point
# ============================================================


async def main():
    """CLI 엔트리 포인트"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python agents/new_agent.py <bicep_file_path> [output_path]")
        print("Example: python agents/new_agent.py samples/simple.bicep docker-compose.yml")
        sys.exit(1)
    
    bicep_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "docker-compose.yml"
    
    print(f"🔄 Converting Bicep file: {bicep_file}")
    print(f"📝 Output will be saved to: {output_file}")
    print()
    
    await convert_bicep_to_compose(bicep_file, output_file)


if __name__ == "__main__":
    asyncio.run(main())
