"""
로컬 환경 구현 및 자동 공격 수행 Agent

Bicep 코드를 분석하여 Docker Compose로 로컬 환경을 구축하고,
실제 보안 공격을 수행하는 독립적인 Agent입니다.

GitHub Copilot SDK를 사용하여 동적 공격 전략을 수립합니다.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docker
import yaml

# GitHub Copilot SDK (선택적 import - 없으면 fallback)
try:
    from copilot import CopilotClient
    from copilot.tools import define_tool
    from pydantic import BaseModel, Field

    COPILOT_AVAILABLE = True
except ImportError:
    COPILOT_AVAILABLE = False
    logging.warning("GitHub Copilot SDK not available. Using fallback strategy engine.")

logger = logging.getLogger(__name__)


# ============================================================
# 데이터 구조
# ============================================================


@dataclass
class VulnerabilityItem:
    """취약점 항목 (API 호환)"""

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
    """공격 시나리오 (API 호환)"""

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
    """RedTeam 분석 전체 결과 (API 호환)"""

    architecture_summary: dict
    vulnerabilities: List[VulnerabilityItem]
    attack_scenarios: List[AttackScenario]
    report: str
    raw_results: dict = field(default_factory=dict)

    @property
    def vulnerability_count(self) -> dict:
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for v in self.vulnerabilities:
            counts[v.severity] = counts.get(v.severity, 0) + 1
        return counts


@dataclass
class BicepResource:
    """Bicep 리소스 정의"""

    name: str
    type: str
    properties: Dict[str, Any]
    location: str = ""
    depends_on: List[str] = field(default_factory=list)


@dataclass
class NetworkConfig:
    """네트워크 구성"""

    subnets: List[Dict[str, str]] = field(default_factory=list)
    security_rules: List[Dict[str, Any]] = field(default_factory=list)
    public_ips: List[str] = field(default_factory=list)


@dataclass
class AttackResult:
    """공격 결과"""

    tool: str
    target: str
    success: bool
    findings: List[str]
    raw_output: str
    timestamp: str


@dataclass
class DeploymentInfo:
    """배포 정보"""

    compose_file: str
    containers: List[Dict[str, str]]
    networks: List[str]
    volumes: List[str]


# ============================================================
# Phase 1: Bicep 파서
# ============================================================


class BicepParser:
    """Bicep 코드 파싱 및 리소스 추출"""

    # Azure 리소스 타입 패턴
    RESOURCE_PATTERN = re.compile(
        r"resource\s+(\w+)\s+'([^']+)'(?:\s*=\s*\{([\s\S]*?)\n\})", re.MULTILINE
    )

    # 리소스 타입별 주요 속성
    RESOURCE_TYPES = {
        "Microsoft.Compute/virtualMachines": "vm",
        "Microsoft.Network/networkSecurityGroups": "nsg",
        "Microsoft.Network/publicIPAddresses": "publicip",
        "Microsoft.Network/virtualNetworks": "vnet",
        "Microsoft.Storage/storageAccounts": "storage",
        "Microsoft.Sql/servers": "sql",
        "Microsoft.Sql/servers/databases": "database",
        "Microsoft.Web/sites": "webapp",
        "Microsoft.KeyVault/vaults": "keyvault",
        "Microsoft.Network/networkInterfaces": "nic",
        "Microsoft.Web/serverfarms": "appserviceplan",
    }

    def __init__(self):
        self.resources: List[BicepResource] = []
        self.network_config = NetworkConfig()

    def parse(self, bicep_code: str) -> Tuple[List[BicepResource], NetworkConfig]:
        """Bicep 코드 파싱"""
        logger.info("Bicep 코드 파싱 시작")

        # 리소스 추출
        matches = self.RESOURCE_PATTERN.finditer(bicep_code)
        for match in matches:
            resource_name = match.group(1)
            resource_type = match.group(2)
            resource_body = match.group(3)

            # 리소스 타입 정규화
            normalized_type = self._normalize_resource_type(resource_type)

            # 속성 추출
            properties = self._extract_properties(resource_body)

            resource = BicepResource(
                name=resource_name, type=normalized_type, properties=properties
            )
            self.resources.append(resource)

            # 네트워크 설정 추출
            if normalized_type == "nsg":
                self._extract_nsg_rules(resource_body)
            elif normalized_type == "vnet":
                self._extract_subnets(resource_body)
            elif normalized_type == "publicip":
                self.network_config.public_ips.append(resource_name)

        logger.info(
            f"파싱 완료: {len(self.resources)}개 리소스, "
            f"{len(self.network_config.security_rules)}개 NSG 규칙"
        )

        return self.resources, self.network_config

    def _normalize_resource_type(self, resource_type: str) -> str:
        """리소스 타입 정규화"""
        for full_type, short_name in self.RESOURCE_TYPES.items():
            if full_type in resource_type:
                return short_name
        return resource_type

    def _extract_properties(self, body: str) -> Dict[str, Any]:
        """리소스 속성 추출 (간단한 키-값 파싱)"""
        properties = {}

        # adminUsername, adminPassword 등
        for line in body.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("//"):
                key_value = line.split(":", 1)
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip().rstrip(",")
                    properties[key] = value

        return properties

    def _extract_nsg_rules(self, body: str):
        """NSG 보안 규칙 추출"""
        # securityRules 배열 찾기
        rules_match = re.search(r"securityRules:\s*\[([\s\S]*?)\]", body)
        if not rules_match:
            return

        rules_text = rules_match.group(1)

        # 각 규칙 파싱
        rule_blocks = re.finditer(r"\{([\s\S]*?)\}(?:\s*,|\s*\])", rules_text)
        for rule_block in rule_blocks:
            rule_text = rule_block.group(1)
            rule = {}

            # 규칙 속성 추출
            for key in [
                "name",
                "priority",
                "direction",
                "access",
                "protocol",
                "sourcePortRange",
                "destinationPortRange",
                "sourceAddressPrefix",
                "destinationAddressPrefix",
            ]:
                pattern = rf"{key}:\s*'?([^'\n,]+)'?"
                match = re.search(pattern, rule_text)
                if match:
                    rule[key] = match.group(1).strip("'")

            if rule:
                self.network_config.security_rules.append(rule)

    def _extract_subnets(self, body: str):
        """서브넷 추출"""
        subnets_match = re.search(r"subnets:\s*\[([\s\S]*?)\]", body)
        if not subnets_match:
            return

        subnets_text = subnets_match.group(1)
        subnet_blocks = re.finditer(r"\{([\s\S]*?)\}", subnets_text)

        for subnet_block in subnet_blocks:
            subnet_text = subnet_block.group(1)
            subnet = {}

            name_match = re.search(r"name:\s*'([^']+)'", subnet_text)
            prefix_match = re.search(r"addressPrefix:\s*'([^']+)'", subnet_text)

            if name_match and prefix_match:
                subnet["name"] = name_match.group(1)
                subnet["prefix"] = prefix_match.group(1)
                self.network_config.subnets.append(subnet)


# ============================================================
# Phase 1: 리소스 매퍼
# ============================================================


class ResourceMapper:
    """Azure 리소스를 Docker 이미지로 매핑"""

    # 리소스 타입별 Docker 이미지 매핑
    RESOURCE_TO_DOCKER = {
        "vm": {
            "image": "ubuntu:22.04",
            "command": "tail -f /dev/null",  # 컨테이너 유지
            "expose": [22, 80, 443, 3389],
        },
        "sql": {
            "image": "mcr.microsoft.com/mssql/server:2022-latest",
            "environment": {
                "ACCEPT_EULA": "Y",
                "MSSQL_SA_PASSWORD": "YourStrong!Passw0rd",  # SQL Server 비밀번호 정책 준수
                "MSSQL_PID": "Developer",
            },
            "expose": [1433],
        },
        "storage": {
            "image": "minio/minio:latest",
            "command": 'server /data --console-address ":9001"',
            "environment": {
                "MINIO_ROOT_USER": "admin",
                "MINIO_ROOT_PASSWORD": "password123",
            },
            "expose": [9000, 9001],
        },
        "webapp": {"image": "nginx:alpine", "expose": [80, 443]},
        "keyvault": {
            "image": "hashicorp/vault:latest",  # vault:latest → hashicorp/vault:latest
            "environment": {
                "VAULT_DEV_ROOT_TOKEN_ID": "root",
                "VAULT_DEV_LISTEN_ADDRESS": "0.0.0.0:8200",
            },
            "expose": [8200],
        },
    }

    def __init__(self, resources: List[BicepResource], network_config: NetworkConfig):
        self.resources = resources
        self.network_config = network_config
        self.service_mapping: Dict[str, Dict] = {}

    def map_to_docker(self) -> Dict[str, Dict]:
        """리소스를 Docker 서비스로 매핑"""
        logger.info("Azure 리소스를 Docker 서비스로 매핑 중")

        # 포트 충돌 방지
        used_host_ports = set()

        for resource in self.resources:
            if resource.type in self.RESOURCE_TO_DOCKER:
                service_name = f"{resource.type}_{resource.name}"
                docker_config = self.RESOURCE_TO_DOCKER[resource.type].copy()

                # NSG 규칙을 포트 매핑으로 변환
                ports = self._get_exposed_ports(resource.type)

                service = {
                    "image": docker_config.get("image"),
                    "container_name": service_name,
                    "networks": ["attack_network"],
                    "restart": "unless-stopped",
                }

                if "command" in docker_config:
                    service["command"] = docker_config["command"]

                if "environment" in docker_config:
                    service["environment"] = docker_config["environment"]

                # 포트 노출 - 충돌 방지
                if ports:
                    port_mappings = []
                    for container_port in ports:
                        host_port = container_port
                        # 이미 사용 중인 포트면 다른 포트 찾기
                        while host_port in used_host_ports:
                            host_port += 1000  # 1000씩 증가 (1433 -> 2433)
                        used_host_ports.add(host_port)
                        port_mappings.append(f"{host_port}:{container_port}")
                    service["ports"] = port_mappings

                self.service_mapping[service_name] = service

        logger.info(f"매핑 완료: {len(self.service_mapping)}개 서비스")
        return self.service_mapping

    def _get_exposed_ports(self, resource_type: str) -> List[int]:
        """NSG 규칙에서 노출된 포트 추출"""
        exposed_ports = set()

        for rule in self.network_config.security_rules:
            if (
                rule.get("direction") == "Inbound"
                and rule.get("access") == "Allow"
                and rule.get("sourceAddressPrefix") == "*"
            ):

                port_range = rule.get("destinationPortRange", "")
                if port_range and port_range != "*":
                    try:
                        port = int(port_range)
                        exposed_ports.add(port)
                    except ValueError:
                        pass

        # 리소스 타입 기본 포트도 추가
        if resource_type in self.RESOURCE_TO_DOCKER:
            default_ports = self.RESOURCE_TO_DOCKER[resource_type].get("expose", [])
            exposed_ports.update(default_ports)

        return sorted(list(exposed_ports))


# ============================================================
# Phase 1: Docker Compose 생성기
# ============================================================


class DockerComposer:
    """Docker Compose 파일 생성"""

    def __init__(self, service_mapping: Dict[str, Dict]):
        self.service_mapping = service_mapping

    def generate_compose_file(self) -> str:
        """docker-compose.yml 생성"""
        logger.info("Docker Compose 파일 생성 중")

        compose = {
            "version": "3.8",
            "services": self.service_mapping,
            "networks": {
                "attack_network": {
                    "driver": "bridge",
                    "ipam": {"config": [{"subnet": "172.20.0.0/16"}]},
                }
            },
        }

        yaml_content = yaml.dump(compose, default_flow_style=False, sort_keys=False)
        logger.info("Docker Compose 파일 생성 완료")
        return yaml_content


# ============================================================
# Phase 1: 로컬 배포자
# ============================================================


class LocalDeployer:
    """Docker Compose 배포 및 관리"""

    def __init__(self):
        try:
            self.docker_client = docker.from_env()
            logger.info("Docker 연결 성공")
        except Exception as e:
            logger.error(f"Docker 연결 실패: {e}")
            raise RuntimeError(
                "Docker가 실행 중이지 않습니다. Docker를 시작한 후 다시 시도하세요."
            )

        self.compose_file_path: Optional[Path] = None
        self.deployment_info: Optional[DeploymentInfo] = None
        self.deployment_failed = False  # 배포 실패 플래그

    def _validate_and_fix_compose_file(self, compose_path: Path) -> bool:
        """
        Docker Compose 파일 검증 및 자동 수정

        Returns:
            bool: 수정 여부
        """
        logger.info("🔍 Docker Compose 파일 검증 및 수정 중...")

        try:
            with open(compose_path, "r") as f:
                compose_data = yaml.safe_load(f)

            fixed = False

            # 1. 포트 충돌 검증 및 수정
            used_ports = set()
            for service_name, service_config in compose_data.get(
                "services", {}
            ).items():
                if "ports" in service_config:
                    new_ports = []
                    for port_mapping in service_config["ports"]:
                        if isinstance(port_mapping, str) and ":" in port_mapping:
                            host_port = int(port_mapping.split(":")[0])
                            container_port = port_mapping.split(":")[1]

                            original_host_port = host_port
                            while host_port in used_ports:
                                host_port += 1000
                                fixed = True

                            if original_host_port != host_port:
                                logger.warning(
                                    f"  ⚠️  포트 충돌 수정: {service_name} {original_host_port} → {host_port}"
                                )

                            used_ports.add(host_port)
                            new_ports.append(f"{host_port}:{container_port}")
                        else:
                            new_ports.append(port_mapping)

                    service_config["ports"] = new_ports

            # 2. 이미지명 검증 및 수정
            image_fixes = {
                "vault:latest": "hashicorp/vault:latest",
                "vault": "hashicorp/vault:latest",
            }

            for service_name, service_config in compose_data.get(
                "services", {}
            ).items():
                if "image" in service_config:
                    original_image = service_config["image"]
                    if original_image in image_fixes:
                        service_config["image"] = image_fixes[original_image]
                        logger.warning(
                            f"  ⚠️  이미지명 수정: {service_name} {original_image} → {service_config['image']}"
                        )
                        fixed = True

            # 3. SQL Server 환경변수 검증 및 수정
            for service_name, service_config in compose_data.get(
                "services", {}
            ).items():
                if "mssql" in service_config.get("image", "").lower():
                    env = service_config.get("environment", {})
                    if isinstance(env, dict):
                        # SA_PASSWORD를 MSSQL_SA_PASSWORD로 변경
                        if "SA_PASSWORD" in env and "MSSQL_SA_PASSWORD" not in env:
                            env["MSSQL_SA_PASSWORD"] = env.pop("SA_PASSWORD")
                            logger.warning(
                                f"  ⚠️  SQL Server 환경변수 수정: {service_name} SA_PASSWORD → MSSQL_SA_PASSWORD"
                            )
                            fixed = True

                        # 비밀번호 강도 검증
                        password = env.get("MSSQL_SA_PASSWORD", "")
                        if (
                            len(password) < 8
                            or not any(c.isupper() for c in password)
                            or not any(c.islower() for c in password)
                            or not any(c.isdigit() for c in password)
                        ):
                            env["MSSQL_SA_PASSWORD"] = "YourStrong!Passw0rd"
                            logger.warning(
                                f"  ⚠️  SQL Server 비밀번호 강화: {service_name}"
                            )
                            fixed = True

            # 수정 사항이 있으면 파일 다시 저장
            if fixed:
                with open(compose_path, "w") as f:
                    yaml.dump(
                        compose_data, f, default_flow_style=False, sort_keys=False
                    )
                logger.info(f"✅ Compose 파일 수정 완료: {compose_path}")
                return True
            else:
                logger.info("✅ 검증 완료: 수정할 사항 없음")
                return False

        except Exception as e:
            logger.error(f"❌ Compose 파일 검증 실패: {e}")
            return False

    def deploy(self, compose_yaml: str) -> DeploymentInfo:
        """Docker Compose로 배포"""
        logger.info("로컬 환경 배포 시작")

        # 임시 파일에 compose 저장
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(compose_yaml)
            self.compose_file_path = Path(f.name)

        logger.info(f"Compose 파일 경로: {self.compose_file_path}")

        # 최대 2회 시도 (초기 시도 + 1회 재시도)
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                # 2회차 시도 전에 파일 검증 및 수정
                if attempt == 2:
                    logger.warning(
                        "⚠️  첫 배포 실패, Compose 파일 검증 후 재시도합니다..."
                    )
                    self._validate_and_fix_compose_file(self.compose_file_path)

                # docker-compose up -d
                logger.info(f"[시도 {attempt}/{max_attempts}] 컨테이너 시작 중...")
                logger.info(
                    "⏱️  이미지 다운로드 및 컨테이너 생성 중 (첫 실행 시 최대 10분 소요)"
                )

                result = subprocess.run(
                    ["docker-compose", "-f", str(self.compose_file_path), "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10분 타임아웃 (이미지 다운로드 시간 포함)
                )

                if result.returncode != 0:
                    logger.error(
                        f"❌ 이미지 다운로드 및 컨테이너 생성 실패 (returncode={result.returncode})"
                    )
                    logger.error(f"Stderr: {result.stderr[:1000]}")

                    # 마지막 시도였으면 실패 처리
                    if attempt == max_attempts:
                        logger.error("❌ 모든 배포 시도 실패. 시뮬레이션을 중단합니다.")
                        self.deployment_failed = True
                        return DeploymentInfo(
                            compose_file=str(self.compose_file_path),
                            containers=[],
                            networks=[],
                            volumes=[],
                        )
                    else:
                        # docker-compose up 실패 시 yml 검증 후 재시도
                        logger.warning("⚠️  Docker Compose 파일 검증 및 수정 중...")
                        self._validate_and_fix_compose_file(self.compose_file_path)
                        time.sleep(2)
                        continue

                # 배포 명령 성공!
                logger.info("✅ 이미지 다운로드 및 컨테이너 생성 완료")

                # 컨테이너 상태 반복 확인 (최대 10분)
                logger.info("⏱️  컨테이너 상태 확인 중... (최대 10분 대기)")
                max_wait_seconds = 600  # 10분
                check_interval = 10  # 10초마다 체크
                elapsed = 0
                containers = []

                while elapsed < max_wait_seconds:
                    containers = self._get_running_containers()

                    if containers:
                        logger.info(
                            f"✅ {len(containers)}개 컨테이너 감지됨 (대기 시간: {elapsed}초)"
                        )
                        break

                    # 컨테이너 상태 로그
                    if elapsed % 30 == 0:  # 30초마다 상태 출력
                        ps_result = subprocess.run(
                            [
                                "docker-compose",
                                "-f",
                                str(self.compose_file_path),
                                "ps",
                                "-a",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        logger.info(
                            f"컨테이너 초기화 중... ({elapsed}/{max_wait_seconds}초)"
                        )
                        if elapsed == 0:
                            logger.debug(f"상태:\n{ps_result.stdout[:500]}")

                    time.sleep(check_interval)
                    elapsed += check_interval

                # 10분 초과 시
                if not containers:
                    logger.warning(f"⚠️  10분 동안 컨테이너 시작 확인 안 됨")

                    # 마지막 시도였으면 실패 처리
                    if attempt == max_attempts:
                        logger.error("❌ 컨테이너 시작 실패. 시뮬레이션을 중단합니다.")
                        self.deployment_failed = True
                        return DeploymentInfo(
                            compose_file=str(self.compose_file_path),
                            containers=[],
                            networks=[],
                            volumes=[],
                        )
                    else:
                        # 10분 초과 시 컨테이너 정리부터 재시도
                        logger.info(f"재시도 준비 중... ({attempt + 1}/{max_attempts})")
                        time.sleep(2)
                        continue

                # 성공! 네트워크 정보 수집
                networks = self._get_networks()

                self.deployment_info = DeploymentInfo(
                    compose_file=str(self.compose_file_path),
                    containers=containers,
                    networks=networks if networks else ["attack_network"],
                    volumes=[],
                )

                logger.info(f"✅ 배포 완료: {len(containers)}개 컨테이너 실행 중")
                return self.deployment_info

            except subprocess.TimeoutExpired:
                logger.error("❌ Docker Compose 배포 타임아웃 (10분 초과)")
                if attempt == max_attempts:
                    self.deployment_failed = True
                    return DeploymentInfo(
                        compose_file=str(self.compose_file_path),
                        containers=[],
                        networks=[],
                        volumes=[],
                    )
                else:
                    logger.info(f"타임아웃 후 재시도... ({attempt + 1}/{max_attempts})")
                    time.sleep(2)
                    continue

            except Exception as e:
                logger.error(f"배포 중 예외 발생: {e}", exc_info=True)
                if attempt == max_attempts:
                    self.deployment_failed = True
                    return DeploymentInfo(
                        compose_file=str(self.compose_file_path),
                        containers=[],
                        networks=[],
                        volumes=[],
                    )
                else:
                    logger.info(f"예외 후 재시도... ({attempt + 1}/{max_attempts})")
                    time.sleep(2)
                    continue

        # 여기 도달하면 모든 시도 실패
        logger.error("❌ 모든 배포 시도 실패")
        self.deployment_failed = True
        return DeploymentInfo(
            compose_file=str(self.compose_file_path) if self.compose_file_path else "",
            containers=[],
            networks=[],
            volumes=[],
        )

    def _get_running_containers(self) -> List[Dict[str, str]]:
        """실행 중인 컨테이너 정보 (subprocess 기반)"""
        try:
            # docker-compose ps -q로 컨테이너 ID 목록 가져오기
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file_path), "ps", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"docker-compose ps 실패: {result.stderr}")
                return []

            container_ids = result.stdout.strip().split("\n")
            container_ids = [cid for cid in container_ids if cid]  # 빈 문자열 제거

            if not container_ids:
                return []

            # 각 컨테이너의 상세 정보 가져오기
            containers = []
            for container_id in container_ids:
                try:
                    inspect_result = subprocess.run(
                        ["docker", "inspect", container_id],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if inspect_result.returncode != 0:
                        continue

                    import json

                    container_data = json.loads(inspect_result.stdout)[0]

                    # 상태가 running인지 확인
                    state = container_data.get("State", {})
                    if state.get("Status") != "running":
                        continue

                    # 네트워크 정보 찾기
                    networks = container_data.get("NetworkSettings", {}).get(
                        "Networks", {}
                    )
                    ip_address = "N/A"
                    for network_name, network_info in networks.items():
                        if "attack_network" in network_name:
                            ip_address = network_info.get("IPAddress", "N/A")
                            break

                    # 이미지 이름
                    image = container_data.get("Config", {}).get("Image", "unknown")

                    containers.append(
                        {
                            "id": container_id[:12],
                            "name": container_data.get("Name", "").lstrip("/"),
                            "image": image,
                            "ip": ip_address,
                            "status": state.get("Status", "unknown"),
                        }
                    )

                except Exception as e:
                    logger.debug(f"컨테이너 {container_id} 정보 수집 실패: {e}")
                    continue

            return containers

        except Exception as e:
            logger.error(f"컨테이너 목록 조회 실패: {e}")
            return []

    def _get_networks(self) -> List[str]:
        """네트워크 목록"""
        networks = []
        for network in self.docker_client.networks.list():
            if "attack" in network.name:
                networks.append(network.name)
        return networks

    def cleanup(self):
        """배포 환경 정리 - 모든 컨테이너 제거"""
        logger.info("🧹 모든 실행 중인 컨테이너 정리 중...")
        try:
            # 실행 중인 모든 컨테이너 중지
            subprocess.run(
                "docker stop $(docker ps -q) 2>/dev/null || true",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # 모든 컨테이너 제거
            subprocess.run(
                "docker rm $(docker ps -aq) 2>/dev/null || true",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # compose 파일 관련 리소스 정리
            if self.compose_file_path and self.compose_file_path.exists():
                subprocess.run(
                    ["docker-compose", "-f", str(self.compose_file_path), "down", "-v"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.compose_file_path.unlink()

            logger.info("✅ 정리 완료")
        except Exception as e:
            logger.warning(f"정리 중 오류: {e}")


# ============================================================
# Agent Loop Tool 파라미터 정의 (Pydantic)
# ============================================================

if COPILOT_AVAILABLE:

    class NmapScanParams(BaseModel):
        target: str = Field(
            description="Target IP address or hostname to scan (e.g., '172.18.0.2')"
        )
        port_range: str = Field(
            default="1-1000",
            description="Port range to scan (e.g., '1-1000', '22,80,443')",
        )

    class HydraAttackParams(BaseModel):
        target: str = Field(
            description="Target IP address or hostname with SSH service"
        )
        username: str = Field(
            default="root",
            description="Username to test. Common values: 'root', 'admin', 'ubuntu'",
        )
        password_list: str = Field(
            default="password,123456,admin,root",
            description="Comma-separated password list",
        )

    class SQLMapAttackParams(BaseModel):
        target_url: str = Field(
            description="Target URL with parameter to test (e.g., 'http://172.18.0.2/login?user=test')"
        )
        level: int = Field(
            default=1,
            ge=1,
            le=5,
            description="Test level (1-5). Higher = more thorough but slower",
        )

    class MetasploitExploitParams(BaseModel):
        target: str = Field(description="Target IP address or hostname")
        exploit_module: str = Field(
            default="scanner/portscan/tcp", description="Metasploit module to use"
        )

    class SQLServerAttackParams(BaseModel):
        target: str = Field(
            description="SQL Server target IP address or hostname"
        )
        port: int = Field(
            default=1433,
            description="SQL Server port (default: 1433)"
        )

    class RDPAttackParams(BaseModel):
        target: str = Field(
            description="RDP target IP address or hostname"
        )
        port: int = Field(
            default=3389,
            description="RDP port (default: 3389)"
        )

    class StorageScanParams(BaseModel):
        target: str = Field(
            description="Storage server IP address or hostname"
        )
        port: int = Field(
            default=9000,
            description="Storage HTTP port (MinIO=9000, Azurite=10000, Azure=443)"
        )


# ============================================================
# Agent Loop (Plan → Act → Observe → Re-plan)
# ============================================================


class CopilotAgentLoop:
    """LLM이 도구를 직접 선택하고 실행하는 Agent Loop"""

    def __init__(self):
        self.client: Optional[Any] = None
        self.session: Optional[Any] = None
        self.available = COPILOT_AVAILABLE

        # 공격 도구 인스턴스
        self.nmap = NmapScanner()
        self.hydra = HydraAttacker()
        self.sqlmap = SQLMapAttacker()
        self.metasploit = MetasploitAttacker()
        self.sqlserver_attacker = SQLServerAttacker()  # 새 도구
        self.rdp_attacker = RDPAttacker()  # 새 도구
        self.storage_scanner = StorageHTTPScanner()  # 새 도구

        # 결과 저장
        self.attack_results: List[AttackResult] = []
        self.attack_history: List[Dict[str, Any]] = []

        # 설정
        self.max_iterations = 15

        # Tool 함수들 (self.tools에 바인딩하기 위해)
        self._init_tools()

    def _init_tools(self):
        """Tool 함수 초기화 (데코레이터 적용)"""
        if not COPILOT_AVAILABLE:
            return

        # Tool 1: Nmap Scanner
        @define_tool(
            description="Scan target IP address or hostname for open ports and running services. Use this as the first step to identify attack surface."
        )
        async def scan_with_nmap(params: NmapScanParams) -> dict:
            logger.info(f"🔧 Nmap 스캔: {params.target} (ports: {params.port_range})")
            result = await self.nmap.scan(params.target, params.port_range)
            self.attack_results.append(result)

            return {
                "success": result.success,
                "target": result.target,
                "findings": result.findings[:10],  # 최대 10개만 반환
                "timestamp": result.timestamp,
            }

        # Tool 2: Hydra SSH Attack
        @define_tool(
            description="Perform SSH brute force attack to test weak credentials. Use after finding open SSH port (22) with nmap."
        )
        async def attack_ssh_with_hydra(params: HydraAttackParams) -> dict:
            logger.info(f"🔧 Hydra SSH 공격: {params.target} (user: {params.username})")
            password_list = params.password_list.split(",")
            result = await self.hydra.attack_ssh(
                params.target, params.username, password_list
            )
            self.attack_results.append(result)

            return {
                "success": result.success,
                "target": result.target,
                "findings": result.findings,
                "timestamp": result.timestamp,
            }

        # Tool 3: SQLMap Attack
        @define_tool(
            description="Test for SQL injection vulnerabilities in web applications. Use after finding open web ports (80, 443) with nmap."
        )
        async def attack_sql_with_sqlmap(params: SQLMapAttackParams) -> dict:
            logger.info(f"🔧 SQLMap 공격: {params.target_url}")
            result = await self.sqlmap.attack(params.target_url)
            self.attack_results.append(result)

            return {
                "success": result.success,
                "target": result.target,
                "findings": result.findings,
                "timestamp": result.timestamp,
            }

        # Tool 4: Metasploit Exploit
        @define_tool(
            description="Exploit known vulnerabilities using Metasploit framework. Use after identifying specific services/versions with nmap."
        )
        async def exploit_with_metasploit(params: MetasploitExploitParams) -> dict:
            logger.info(
                f"🔧 Metasploit 익스플로잇: {params.target} (module: {params.exploit_module})"
            )
            result = await self.metasploit.exploit(params.target, params.exploit_module)
            self.attack_results.append(result)

            return {
                "success": result.success,
                "target": result.target,
                "findings": result.findings,
                "timestamp": result.timestamp,
            }

        # Tool 5: SQL Server Attack (NEW)
        @define_tool(
            description="Perform SQL Server authentication brute force attack. Use after finding open port 1433 with nmap. Tests common SQL Server credentials."
        )
        async def attack_sqlserver(params: SQLServerAttackParams) -> dict:
            logger.info(f"🔧 SQL Server 공격: {params.target}:{params.port}")
            result = await self.sqlserver_attacker.attack(params.target, params.port)
            self.attack_results.append(result)

            return {
                "success": result.success,
                "target": result.target,
                "findings": result.findings,
                "timestamp": result.timestamp,
            }

        # Tool 6: RDP Attack (NEW)
        @define_tool(
            description="Perform RDP brute force attack. Use after finding open port 3389 with nmap. Tests common Windows credentials."
        )
        async def attack_rdp(params: RDPAttackParams) -> dict:
            logger.info(f"🔧 RDP 공격: {params.target}:{params.port}")
            result = await self.rdp_attacker.attack(params.target, params.port)
            self.attack_results.append(result)

            return {
                "success": result.success,
                "target": result.target,
                "findings": result.findings,
                "timestamp": result.timestamp,
            }

        # Tool 7: Storage HTTP Scanner (NEW)
        @define_tool(
            description="Scan HTTP storage endpoint (MinIO/S3/Azure) for public access vulnerabilities. Tests anonymous access to buckets/containers. Use after finding storage ports (9000, 10000, etc.) with nmap."
        )
        async def scan_storage_http(params: StorageScanParams) -> dict:
            logger.info(f"🔧 스토리지 HTTP 스캔: {params.target}:{params.port}")
            result = await self.storage_scanner.scan(params.target, params.port)
            self.attack_results.append(result)

            return {
                "success": result.success,
                "target": result.target,
                "findings": result.findings,
                "timestamp": result.timestamp,
            }

        # Tool 리스트 저장
        self.tools = [
            scan_with_nmap,
            attack_ssh_with_hydra,
            attack_sql_with_sqlmap,
            exploit_with_metasploit,
            attack_sqlserver,  # 새 도구
            attack_rdp,  # 새 도구
            scan_storage_http,  # 새 도구 (수정됨)
        ]

    async def initialize(self):
        """Copilot 클라이언트 초기화 및 도구 등록"""
        if not self.available:
            logger.warning("Copilot SDK 사용 불가, Fallback 모드")
            return

        try:
            logger.info("Agent Loop용 Copilot SDK 초기화 중...")
            self.client = CopilotClient()
            await self.client.start()

            # 세션 생성 시 도구 전달
            self.session = await self.client.create_session(
                {
                    "model": "gpt-4.1",
                    "streaming": False,
                    "tools": self.tools,
                }
            )

            logger.info(f"Agent Loop 초기화 완료 ({len(self.tools)}개 도구 등록)")

        except Exception as e:
            logger.error(f"Agent Loop 초기화 실패: {e}")
            self.available = False

    async def run_agent_loop(
        self, deployment_info: DeploymentInfo, network_config: NetworkConfig
    ) -> List[AttackResult]:
        """Agent Loop 실행: Plan → Act → Observe → Re-plan"""

        if not self.available or not self.session:
            logger.warning("Agent Loop 사용 불가, Fallback 모드로 전환")
            return await self._fallback_attack(deployment_info)

        logger.info("🔄 Agent Loop 시작 (최대 {}회 반복)".format(self.max_iterations))

        # 초기 컨텍스트 생성
        context = self._build_initial_context(deployment_info, network_config)

        # Agent Loop: 여러 번 프롬프트를 보내며 도구 사용
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"\n━━━ Iteration {iteration}/{self.max_iterations} ━━━")

            try:
                # 이전 공격 결과 개수
                prev_count = len(self.attack_results)

                # 🔍 중복 방지: 이미 충분히 스캔했으면 경고
                nmap_count = sum(1 for r in self.attack_results if r.tool == "nmap")
                if nmap_count >= 6 and prev_count == nmap_count:
                    logger.warning(f"⚠️ Nmap만 {nmap_count}번 수행됨. 다른 도구로 전환 필요.")
                    context += "\n\n**MANDATORY**: Reconnaissance is complete. You MUST now use ALL of the following attack tools on the targets — regardless of nmap results:\n- attack_ssh_with_hydra\n- attack_sqlserver\n- attack_rdp\n- attack_sql_with_sqlmap\n- scan_storage_http\n- exploit_with_metasploit\n\nDo NOT say COMPLETE until all of these have been used at least once.\n\n"

                # LLM에게 다음 행동 요청 (SDK가 자동으로 tool 호출)
                response = await self.session.send_and_wait({"prompt": context}, timeout=180.0)

                # 새로운 공격이 수행되었는지 확인
                new_count = len(self.attack_results)
                if new_count > prev_count:
                    # 도구가 실행됨 - 결과를 컨텍스트에 추가
                    for result in self.attack_results[prev_count:]:
                        context += self._format_tool_result(result, iteration)

                        if result.success:
                            logger.warning(
                                f"🎯 [Iteration {iteration}] 공격 성공: {result.tool} on {result.target}"
                            )
                        else:
                            logger.info(
                                f"ℹ️  [Iteration {iteration}] 공격 실패: {result.tool} on {result.target}"
                            )
                else:
                    # 도구가 실행되지 않음 - LLM이 텍스트만 응답
                    if hasattr(response, "data") and hasattr(response.data, "content"):
                        content = response.data.content
                        logger.info(f"💭 LLM 응답: {content}...")

                        # 아직 사용하지 않은 필수 도구가 있으면 COMPLETE 무시
                        used_tools = {r.tool for r in self.attack_results}
                        mandatory_tools = {"hydra", "sqlserver", "rdp", "sqlmap", "storage_scan"}
                        missing_tools = mandatory_tools - used_tools

                        # 종료 키워드 확인 (필수 도구를 모두 사용한 경우만 허용)
                        if any(
                            keyword in content.lower()
                            for keyword in ["complete", "finish", "done", "완료", "종료"]
                        ):
                            if missing_tools:
                                logger.warning(
                                    f"⚠️ LLM이 COMPLETE 시도했지만 미사용 도구 있음: {missing_tools}. 강제 계속."
                                )
                                context += (
                                    f"\n\n**OVERRIDE**: You said COMPLETE but these tools have NOT been used yet: {missing_tools}. "
                                    f"You MUST use each of them before finishing. Pick one and use it now.\n\n"
                                )
                            else:
                                logger.info(f"✅ LLM이 공격 종료 결정 (Iteration {iteration})")
                                break

                        # 컨텍스트에 LLM 사고 과정 추가
                        context += f"\n\n**Agent's Analysis (Iteration {iteration}):**\n{content}\n\nContinue with your next action.\n"
                    else:
                        logger.warning(
                            f"⚠️ 예상치 못한 응답 형태 (Iteration {iteration})"
                        )
                        break

            except Exception as e:
                logger.error(f"❌ Iteration {iteration} 실패: {e}", exc_info=True)
                break

        # ── 강제 실행 단계: Agent Loop 이후 미사용 도구를 코드 레벨에서 강제 실행 ──
        await self._run_mandatory_attacks(deployment_info)

        logger.info(f"\n✅ Agent Loop 완료: 총 {len(self.attack_results)}개 공격 수행")
        return self.attack_results

    async def _run_mandatory_attacks(self, deployment_info: DeploymentInfo) -> None:
        """Agent Loop 완료 후 미사용 도구를 모든 컨테이너에 강제 실행"""
        targets = [c for c in deployment_info.containers if c.get("ip")]
        if not targets:
            return

        used_tool_target_pairs = {(r.tool, r.target.split(":")[0]) for r in self.attack_results}

        # 도구명 → (공격 함수, 포트) 매핑
        mandatory = [
            ("hydra",        lambda ip: self.hydra.attack_ssh(ip)),
            ("sqlserver",    lambda ip: self.sqlserver_attacker.attack(ip, 1433)),
            ("rdp",          lambda ip: self.rdp_attacker.attack(ip, 3389)),
            ("sqlmap",       lambda ip: self.sqlmap.attack(f"http://{ip}/")),
            ("storage_scan", lambda ip: self.storage_scanner.scan(ip, 9000)),
            ("metasploit",   lambda ip: self.metasploit.exploit(ip)),
        ]

        for tool_name, attack_fn in mandatory:
            # 해당 도구를 한 번도 쓰지 않은 타겟에만 실행
            untested = [
                c for c in targets
                if (tool_name, c["ip"]) not in used_tool_target_pairs
            ]
            if not untested:
                continue

            # 첫 번째 타겟에만 실행 (대표 샘플링)
            target_ip = untested[0]["ip"]
            logger.info(f"🔒 [필수 실행] {tool_name} → {target_ip}")
            try:
                result = await attack_fn(target_ip)
                self.attack_results.append(result)
                if result.success:
                    logger.warning(f"🎯 [필수 실행] 성공: {tool_name} on {target_ip}")
                else:
                    logger.info(f"ℹ️  [필수 실행] 완료(실패): {tool_name} on {target_ip}")
            except Exception as e:
                logger.error(f"❌ [필수 실행] {tool_name} 오류: {e}")

    def _build_initial_context(
        self, deployment_info: DeploymentInfo, network_config: NetworkConfig
    ) -> str:
        """초기 컨텍스트 생성"""

        # 타겟 목록
        targets = [c for c in deployment_info.containers if c.get("ip")]
        targets_str = "\n".join(
            [f"  - {c['name']}: {c['ip']} ({c['image']})" for c in targets]
        )

        # 네트워크 규칙
        rules_str = (
            "\n".join(
                [
                    f"  - {rule.get('name', 'unnamed')}: {rule.get('access', 'N/A')} "
                    f"{rule.get('protocol', 'N/A')} port {rule.get('destinationPortRange', 'N/A')} "
                    f"from {rule.get('sourceAddressPrefix', 'N/A')}"
                    for rule in network_config.security_rules[:5]  # 최대 5개만
                ]
            )
            if network_config.security_rules
            else "  - No specific rules defined"
        )

        # 필수 실행 체크리스트 문자열
        mandatory_list = "\n".join([
            "  - [ ] scan_with_nmap (reconnaissance)",
            "  - [ ] attack_ssh_with_hydra",
            "  - [ ] attack_sqlserver",
            "  - [ ] attack_rdp",
            "  - [ ] attack_sql_with_sqlmap",
            "  - [ ] scan_storage_http",
            "  - [ ] exploit_with_metasploit",
        ])

        context = f"""You are an AI penetration testing agent conducting a COMPREHENSIVE security audit.

## Current Environment

**Deployed Targets ({len(targets)} containers):**
{targets_str}

**Network Security Rules:**
{rules_str}

**Network:** {', '.join(deployment_info.networks)}

## Available Tools

1. **scan_with_nmap**: Port scanning and service detection
2. **attack_ssh_with_hydra**: SSH brute force attack (port 22)
3. **attack_sql_with_sqlmap**: SQL injection testing (port 80/443)
4. **exploit_with_metasploit**: Exploit known vulnerabilities
5. **attack_sqlserver**: SQL Server brute force (port 1433)
6. **attack_rdp**: RDP brute force (port 3389)
7. **scan_storage_http**: Storage HTTP endpoint scanner (port 9000/10000)

## MANDATORY TOOL CHECKLIST

You MUST use ALL of the following tools before saying COMPLETE. This is a comprehensive security audit — **do NOT skip any tool regardless of nmap results**:

{mandatory_list}

## Execution Order

1. **Reconnaissance** (1 nmap scan per target, do NOT repeat on same target):
   - Scan each target IP once with nmap
2. **Mandatory Attacks** (run ALL tools below on at least ONE target, regardless of nmap results):
   - attack_ssh_with_hydra → test SSH credentials (services may be accessible even if nmap shows no ports)
   - attack_sqlserver → test SQL Server authentication
   - attack_rdp → test RDP credentials
   - attack_sql_with_sqlmap → test for SQL injection
   - scan_storage_http → scan storage endpoints
   - exploit_with_metasploit → attempt known exploits
3. **COMPLETE** → say this ONLY after ALL 7 tools have been used at least once

## Rules

- **NEVER say COMPLETE** until all 7 tools in the checklist above are used
- **One tool call per response** — do not call the same tool+target twice
- **Nmap limit**: scan each IP only once
- Even if nmap finds no open ports, you MUST still run all attack tools (services may be accessible via direct connection)

## Attack History

(No attacks performed yet. Start with nmap on the first target.)

---

Begin. Your first action: scan the FIRST target with nmap.
"""

        return context

    def _format_tool_result(self, result: AttackResult, iteration: int) -> str:
        """도구 실행 결과를 컨텍스트 형식으로 변환"""

        findings_str = "\n  ".join(result.findings[:10])
        if len(result.findings) > 10:
            findings_str += f"\n  ... ({len(result.findings) - 10} more)"

        status = "✅ SUCCESS" if result.success else "❌ FAILED"

        raw_preview = ""
        if result.tool == "nmap" and result.raw_output:
            raw_preview = f"\n\n**Raw Output Preview:**\n```\n{result.raw_output[:500]}\n```\n"

        # 남은 필수 도구 체크리스트
        all_mandatory = ["hydra", "sqlserver", "rdp", "sqlmap", "storage_scan", "metasploit"]
        used_tools = {r.tool for r in self.attack_results}
        remaining = [t for t in all_mandatory if t not in used_tools]
        checklist_str = (
            "**Remaining mandatory tools (MUST use before COMPLETE):** " + ", ".join(remaining)
            if remaining
            else "**All mandatory tools have been used. You may now say COMPLETE.**"
        )

        formatted = f"""

## Iteration {iteration} Result

**Tool**: {result.tool}
**Target**: {result.target}
**Status**: {status}

**Key Findings:**
  {findings_str}{raw_preview}

---

{checklist_str}

**Next Action Guidance:**
{self._get_next_action_hint(result)}

Pick the next tool from the remaining list above and use it now.
"""

        return formatted

    def _get_next_action_hint(self, result: AttackResult) -> str:
        """이전 결과 기반으로 다음 행동 힌트 제공"""

        # Nmap 스캔 후 힌트
        if result.tool == "nmap":
            nmap_count = sum(
                1 for r in self.attack_results
                if r.tool == "nmap" and r.target == result.target
            )
            if nmap_count > 1:
                return "⚠️ Already scanned this target. Move on to attack tools."

            has_ssh = any("22" in f for f in result.findings)
            has_rdp = any("3389" in f for f in result.findings)
            has_sql = any("1433" in f for f in result.findings)
            has_web = any("80" in f or "443" in f for f in result.findings)
            has_storage = any("9000" in f or "10000" in f for f in result.findings)

            hints = []
            if has_ssh:
                hints.append("Port 22 open → use attack_ssh_with_hydra")
            if has_rdp:
                hints.append("Port 3389 open → use attack_rdp")
            if has_sql:
                hints.append("Port 1433 open → use attack_sqlserver")
            if has_web:
                hints.append("Port 80/443 open → use attack_sql_with_sqlmap")
            if has_storage:
                hints.append("Port 9000/10000 open → use scan_storage_http")

            if hints:
                return "Discovered services:\n  - " + "\n  - ".join(hints)
            else:
                return (
                    "No open ports found — but you MUST still run all attack tools. "
                    "Pick the next tool from the mandatory checklist above."
                )

        # 공격 도구 실행 후
        status = "succeeded" if result.success else "failed"
        return f"{result.tool} {status}. Pick the next tool from the mandatory checklist."

    async def _fallback_attack(
        self, deployment_info: DeploymentInfo
    ) -> List[AttackResult]:
        """Copilot SDK 없을 때 Nmap으로 모든 컨테이너 스캔 (Fallback)"""
        logger.info("Fallback 모드: Nmap으로 모든 컨테이너 스캔")
        results = []
        for container in deployment_info.containers:
            ip = container.get("ip")
            if not ip:
                continue
            result = await self.nmap.scan(ip)
            results.append(result)
            self.attack_results.append(result)
        return results

    async def cleanup(self):
        """Copilot 세션 종료"""
        if self.client:
            await self.client.stop()


# ============================================================
# 메인 Agent 클래스 (통합)
# ============================================================


class LocalAttackAgent:
    """Bicep 로컬 구현 및 자동 공격 Agent"""

    def __init__(self, use_docker: bool = True):
        self.parser = BicepParser()
        self.deployer = LocalDeployer()
        self.agent_loop = CopilotAgentLoop()  # Agent Loop 사용

        self.resources: List[BicepResource] = []
        self.network_config: Optional[NetworkConfig] = None
        self.deployment_info: Optional[DeploymentInfo] = None
        self.attack_results: List[AttackResult] = []

    async def analyze_and_attack(self, bicep_code: str) -> Dict[str, Any]:
        """전체 분석 및 공격 실행"""
        logger.info("=" * 60)
        logger.info("로컬 공격 Agent 시작")
        logger.info("=" * 60)

        try:
            # Phase 1: 파싱 및 배포
            logger.info("\n[Phase 1] Bicep 파싱 및 로컬 배포")
            self.resources, self.network_config = self.parser.parse(bicep_code)

            mapper = ResourceMapper(self.resources, self.network_config)
            service_mapping = mapper.map_to_docker()

            composer = DockerComposer(service_mapping)
            compose_yaml = composer.generate_compose_file()

            self.deployment_info = self.deployer.deploy(compose_yaml)

            # Phase 2-4: Agent Loop 공격 실행
            logger.info("\n[Phase 2] Agent Loop 초기화 및 공격 실행")
            await self.agent_loop.initialize()
            self.attack_results = await self.agent_loop.run_agent_loop(
                self.deployment_info, self.network_config
            )
            await self.agent_loop.cleanup()

            # Phase 5: 결과 분석 및 보고서 생성
            logger.info("\n[Phase 3] 결과 분석 및 보고서 생성")
            analyzer = ResultAnalyzer()
            analysis = analyzer.analyze(self.attack_results)

            # LLM 기반 보고서 생성
            generator = ReportGenerator()
            await generator.initialize()
            report = await generator.generate(
                analysis, self.deployment_info, self.resources
            )
            await generator.cleanup()

            # 결과 반환
            return {
                "success": True,
                "resources_parsed": len(self.resources),
                "containers_deployed": len(self.deployment_info.containers),
                "attacks_executed": len(self.attack_results),
                "successful_attacks": analysis["successful_attacks"],
                "critical_findings": len(analysis["critical_findings"]),
                "analysis": analysis,
                "report": report,
                "deployment_info": {
                    "containers": self.deployment_info.containers,
                    "networks": self.deployment_info.networks,
                },
                "message": "전체 파이프라인 완료: 배포 → Agent Loop 공격 → 보고서 생성 성공",
            }

        except Exception as e:
            logger.error(f"Agent 실행 중 오류: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

        finally:
            # 정리 (Agent Loop은 이미 cleanup 호출됨)
            pass

    async def analyze(self, bicep_code: str) -> AnalysisResult:
        """
        API 호환 메서드: Bicep 코드 분석 및 공격 수행
        
        analyze_and_attack()를 호출하고 결과를 AnalysisResult로 변환하여 반환합니다.
        기존 API 엔드포인트와 호환됩니다.
        """
        logger.info("RedTeam 분석 시작 (LocalAttackAgent)")
        
        # 실제 공격 수행
        result = await self.analyze_and_attack(bicep_code)
        
        if not result.get("success"):
            # 실패 시 빈 결과 반환
            return AnalysisResult(
                architecture_summary={"resources": [], "resource_count": 0},
                vulnerabilities=[],
                attack_scenarios=[],
                report=f"## 분석 실패\n\n오류: {result.get('error', 'Unknown error')}",
                raw_results=result,
            )
        
        # 성공 시 변환
        return self._convert_to_analysis_result(result)
    
    def _convert_to_analysis_result(self, result: Dict[str, Any]) -> AnalysisResult:
        """
        analyze_and_attack() 결과를 AnalysisResult로 변환
        """
        # 아키텍처 요약
        architecture_summary = {
            "resources": [
                {"name": r.name, "type": r.type} for r in self.resources
            ],
            "resource_count": len(self.resources),
            "containers_deployed": result.get("containers_deployed", 0),
        }
        
        # AttackResult → VulnerabilityItem 변환
        vulnerabilities = self._convert_to_vulnerabilities(self.attack_results)
        
        # AttackResult → AttackScenario 변환
        attack_scenarios = self._convert_to_attack_scenarios(self.attack_results)
        
        # 보고서는 이미 생성됨
        report = result.get("report", "")
        
        return AnalysisResult(
            architecture_summary=architecture_summary,
            vulnerabilities=vulnerabilities,
            attack_scenarios=attack_scenarios,
            report=report,
            raw_results={
                "model": "LocalAttackAgent-CopilotAgentLoop",
                "attacks_executed": result.get("attacks_executed", 0),
                "successful_attacks": result.get("successful_attacks", 0),
                "critical_findings": result.get("critical_findings", 0),
            },
        )
    
    def _convert_to_vulnerabilities(
        self, attack_results: List[AttackResult]
    ) -> List[VulnerabilityItem]:
        """AttackResult를 VulnerabilityItem으로 변환"""
        vulnerabilities = []
        vuln_id = 1
        
        for attack in attack_results:
            if not attack.success:
                continue

            # nmap은 실제 open port가 발견된 경우만 취약점으로 등록
            if attack.tool == "nmap" and not any(
                "open port:" in f.lower() for f in attack.findings
            ):
                continue

            # 성공한 공격은 취약점으로 간주
            severity = self._determine_severity(attack.tool, attack.findings)
            
            vuln = VulnerabilityItem(
                id=f"VULN-{vuln_id:03d}",
                severity=severity,
                category=self._attack_to_category(attack.tool),
                affected_resource=attack.target,
                title=f"{attack.tool} 공격 성공: {attack.target}",
                description=f"{attack.tool}을(를) 사용한 공격이 성공했습니다.",
                evidence=self._format_evidence(attack),
                remediation=self._get_remediation(attack.tool),
                benchmark_ref=self._get_benchmark_ref(attack.tool),
            )
            vulnerabilities.append(vuln)
            vuln_id += 1

        # attack_scenarios 변환 시 참조할 수 있도록 저장
        self._last_vulnerabilities = vulnerabilities
        return vulnerabilities

    def _convert_to_attack_scenarios(
        self, attack_results: List[AttackResult]
    ) -> List[AttackScenario]:
        """AttackResult를 AttackScenario로 변환"""
        scenarios = []
        scenario_id = 1
        
        # 성공한 공격들을 그룹핑하여 시나리오 생성
        successful_attacks = [a for a in attack_results if a.success]
        
        for attack in successful_attacks:
            scenario = AttackScenario(
                id=f"ATTACK-{scenario_id:03d}",
                name=self._get_attack_scenario_name(attack.tool),
                mitre_technique=self._get_mitre_technique(attack.tool),
                target_vulnerabilities=self._get_related_vulnerabilities(attack),
                severity=self._determine_severity(attack.tool, attack.findings),
                prerequisites=self._get_prerequisites(attack.tool),
                attack_chain=self._build_attack_chain(attack),
                expected_impact=self._get_expected_impact(attack.tool),
                detection_difficulty="Medium",
                likelihood="High" if attack.success else "Medium",
            )
            scenarios.append(scenario)
            scenario_id += 1
        
        return scenarios
    
    def _determine_severity(self, tool: str, findings: List[str]) -> str:
        """공격 도구와 발견사항을 기반으로 심각도 판단"""
        if tool in ["sqlmap", "metasploit"]:
            return "Critical"
        elif tool in ["hydra", "sqlserver", "rdp"]:
            return "High"
        elif tool in ["nmap"] and any("open port:" in f.lower() for f in findings):
            return "Medium"
        elif tool in ["storage_scan"]:
            return "High"
        return "Low"

    def _attack_to_category(self, tool: str) -> str:
        """공격 도구를 카테고리로 변환"""
        mapping = {
            "nmap": "Network Scanning",
            "hydra": "Authentication",
            "sqlmap": "SQL Injection",
            "metasploit": "Exploitation",
            "sqlserver": "Authentication",
            "rdp": "Authentication",
            "storage_scan": "Data Exposure",
        }
        return mapping.get(tool, "Unknown")
    
    def _format_evidence(self, attack: AttackResult) -> str:
        """공격 결과를 증거 문자열로 포맷"""
        evidence = f"Tool: {attack.tool}\nTarget: {attack.target}\n"
        if attack.findings:
            evidence += "\nFindings:\n"
            for f in attack.findings[:5]:  # 최대 5개만
                evidence += f"- {f}\n"
        return evidence
    
    def _get_remediation(self, tool: str) -> str:
        """공격 도구별 권장 조치"""
        remediation_map = {
            "nmap": "불필요한 포트를 차단하고, 방화벽 규칙을 강화하세요.",
            "hydra": "강력한 비밀번호 정책을 적용하고, 계정 잠금 메커니즘을 활성화하세요.",
            "sqlmap": "SQL Injection 방어 코드를 추가하고, 파라미터화된 쿼리를 사용하세요.",
            "metasploit": "최신 보안 패치를 적용하고, 취약한 서비스를 업데이트하세요.",
            "sqlserver": "SQL Server SA 계정을 비활성화하고, 강력한 비밀번호와 계정 잠금 정책을 적용하세요.",
            "rdp": "RDP 접근을 VPN 또는 특정 IP로 제한하고, NLA(Network Level Authentication)를 활성화하세요.",
            "storage_scan": "스토리지 버킷 공개 접근을 비활성화하고, HTTPS를 강제 적용하세요.",
        }
        return remediation_map.get(tool, "보안 전문가와 상담하세요.")

    def _get_benchmark_ref(self, tool: str) -> str:
        """공격 도구별 벤치마크 참조"""
        benchmark_map = {
            "nmap": "CIS Azure 1.0 - NS-1",
            "hydra": "CIS Azure 1.0 - IAM-2",
            "sqlmap": "CIS Azure 1.0 - APP-3",
            "metasploit": "CIS Azure 1.0 - SEC-1",
            "sqlserver": "CIS Azure 1.0 - IAM-3",
            "rdp": "CIS Azure 1.0 - NS-2",
            "storage_scan": "CIS Azure 1.0 - DS-1",
        }
        return benchmark_map.get(tool, "")

    def _get_attack_scenario_name(self, tool: str) -> str:
        """공격 도구별 시나리오 이름"""
        names = {
            "nmap": "네트워크 스캐닝을 통한 공격 표면 탐지",
            "hydra": "무차별 대입 공격을 통한 인증 우회",
            "sqlmap": "SQL Injection을 통한 데이터베이스 접근",
            "metasploit": "알려진 취약점을 통한 시스템 장악",
            "sqlserver": "SQL Server 무차별 대입 공격을 통한 DB 접근",
            "rdp": "RDP 무차별 대입 공격을 통한 원격 접속",
            "storage_scan": "스토리지 공개 접근을 통한 데이터 노출",
        }
        return names.get(tool, f"{tool} 공격")

    def _get_mitre_technique(self, tool: str) -> str:
        """공격 도구별 MITRE ATT&CK 기법"""
        techniques = {
            "nmap": "T1046 - Network Service Scanning",
            "hydra": "T1110 - Brute Force",
            "sqlmap": "T1190 - Exploit Public-Facing Application",
            "metasploit": "T1210 - Exploitation of Remote Services",
            "sqlserver": "T1110.001 - Password Guessing",
            "rdp": "T1110.001 - Password Guessing",
            "storage_scan": "T1530 - Data from Cloud Storage",
        }
        return techniques.get(tool, "T1000 - Unknown")
    
    def _get_related_vulnerabilities(self, attack: AttackResult) -> List[str]:
        """공격과 관련된 취약점 ID 목록 (tool + target 기반 결정적 매핑)"""
        # 성공한 공격 결과에서 같은 tool/target의 취약점 ID 찾기
        matched = []
        for vuln in self._last_vulnerabilities if hasattr(self, "_last_vulnerabilities") else []:
            if attack.target in vuln.affected_resource or attack.tool in vuln.category.lower():
                matched.append(vuln.id)
        if matched:
            return matched
        # fallback: tool + target 문자열 기반 결정적 ID
        combined = f"{attack.tool}:{attack.target}"
        idx = abs(sum(ord(c) for c in combined)) % 1000
        return [f"VULN-{idx:03d}"]
    
    def _get_prerequisites(self, tool: str) -> str:
        """공격 전제 조건"""
        prereqs = {
            "nmap": "네트워크 접근 권한",
            "hydra": "대상 서비스 접근 및 사용자 이름 목록",
            "sqlmap": "취약한 웹 애플리케이션 엔드포인트",
            "metasploit": "알려진 취약점이 존재하는 서비스",
            "sqlserver": "SQL Server 포트(1433) 접근 및 사용자 이름 목록",
            "rdp": "RDP 포트(3389) 접근 및 Windows 계정 목록",
            "storage_scan": "스토리지 HTTP 엔드포인트 접근",
        }
        return prereqs.get(tool, "대상 시스템 접근 권한")

    def _build_attack_chain(self, attack: AttackResult) -> List[str]:
        """공격 체인 생성"""
        chains = {
            "nmap": [
                "1단계: 대상 IP 범위 확인",
                "2단계: 포트 스캔 수행",
                "3단계: 열린 포트 및 서비스 식별",
                "4단계: 버전 정보 수집",
            ],
            "hydra": [
                "1단계: 대상 인증 서비스 확인",
                "2단계: 사용자 이름 목록 준비",
                "3단계: 비밀번호 사전 준비",
                "4단계: 무차별 대입 공격 수행",
                "5단계: 유효한 자격 증명 획득",
            ],
            "sqlmap": [
                "1단계: 취약한 엔드포인트 식별",
                "2단계: SQL Injection 취약점 확인",
                "3단계: 데이터베이스 정보 추출",
                "4단계: 테이블 및 컬럼 열거",
                "5단계: 데이터 덤프",
            ],
            "metasploit": [
                "1단계: 취약점 식별",
                "2단계: 적절한 익스플로잇 선택",
                "3단계: 페이로드 설정",
                "4단계: 익스플로잇 실행",
                "5단계: 셸 획득 및 권한 상승",
            ],
            "sqlserver": [
                "1단계: SQL Server 포트(1433) 확인",
                "2단계: SA 및 기본 계정 목록 준비",
                "3단계: 비밀번호 사전 공격 수행",
                "4단계: 유효한 SQL Server 자격 증명 획득",
                "5단계: 데이터베이스 접근 및 데이터 추출",
            ],
            "rdp": [
                "1단계: RDP 포트(3389) 확인",
                "2단계: Windows 계정 목록 준비",
                "3단계: 비밀번호 사전 공격 수행",
                "4단계: 유효한 Windows 자격 증명 획득",
                "5단계: 원격 데스크톱 접속 및 시스템 제어",
            ],
            "storage_scan": [
                "1단계: 스토리지 HTTP 엔드포인트 발견",
                "2단계: 익명 접근 시도",
                "3단계: 공개 버킷/컨테이너 열거",
                "4단계: 민감 데이터 다운로드 시도",
            ],
        }
        return chains.get(attack.tool, ["1단계: 공격 수행"])

    def _get_expected_impact(self, tool: str) -> str:
        """예상 영향"""
        impacts = {
            "nmap": "공격 표면 노출, 추가 공격 벡터 발견",
            "hydra": "계정 탈취, 무단 접근",
            "sqlmap": "데이터베이스 전체 탈취, 개인정보 유출",
            "metasploit": "시스템 완전 장악, 내부 네트워크 침투",
            "sqlserver": "데이터베이스 전체 접근, 민감 데이터 유출, 시스템 명령 실행",
            "rdp": "원격 서버 완전 제어, 내부 네트워크 피벗",
            "storage_scan": "민감 파일 및 데이터 유출, 개인정보 노출",
        }
        return impacts.get(tool, "시스템 보안 침해")

    def cleanup(self):
        """환경 정리"""
        self.deployer.cleanup()


# ============================================================
# Phase 3: 공격 도구 통합
# ============================================================


class NmapScanner:
    """Nmap 포트 스캔 및 서비스 탐지"""

    def __init__(self):
        self.tool_available = self._check_nmap()

    def _check_nmap(self) -> bool:
        """Nmap 설치 확인"""
        try:
            result = subprocess.run(
                ["nmap", "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False

    async def scan(
        self, target: str, ports: str = "22,80,443,1433,3389,8200,9000"
    ) -> AttackResult:
        """포트 스캔 실행"""
        logger.info(f"Nmap 스캔 시작: {target}")

        if not self.tool_available:
            logger.error("Nmap이 설치되지 않았습니다. 설치 후 다시 시도하세요.")
            return AttackResult(
                tool="nmap",
                target=target,
                success=False,
                findings=["Nmap not installed"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        try:
            # Nmap 실행: -sV (서비스 버전), -sC (기본 스크립트), -p (포트)
            cmd = ["nmap", "-sV", "-sC", "-p", ports, target]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5분
            )

            findings = self._parse_nmap_output(result.stdout)

            return AttackResult(
                tool="nmap",
                target=target,
                success=result.returncode == 0,
                findings=findings,
                raw_output=result.stdout,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except subprocess.TimeoutExpired:
            logger.error("Nmap 스캔 타임아웃")
            return AttackResult(
                tool="nmap",
                target=target,
                success=False,
                findings=["Scan timed out"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as e:
            logger.error(f"Nmap 스캔 실패: {e}")
            return AttackResult(
                tool="nmap",
                target=target,
                success=False,
                findings=[f"Scan failed: {str(e)}"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    def _parse_nmap_output(self, output: str) -> List[str]:
        """Nmap 출력 파싱"""
        findings = []

        # 디버깅: 전체 출력 로그
        logger.debug(f"Nmap raw output:\n{output}")

        # 오픈 포트 찾기
        for line in output.split("\n"):
            line = line.strip()
            if "/tcp" in line and "open" in line:
                findings.append(f"Open port: {line}")
            elif "/udp" in line and "open" in line:
                findings.append(f"Open port: {line}")
            elif "Service Info:" in line:
                findings.append(f"Service info: {line}")
            # 추가: 포트 스캔 결과 요약 라인도 포함
            elif "PORT" in line and "STATE" in line:
                findings.append(f"Scan header: {line}")

        # 결과가 없으면 "No open ports found"만 반환하는 대신,
        # Nmap이 실행은 되었는지 확인
        if not findings:
            if "Nmap done" in output or "Host is up" in output:
                return ["Host is up, but no open ports found in scanned range"]
            else:
                return ["Scan failed or incomplete - no results"]

        return findings


class HydraAttacker:
    """Hydra 인증 무차별 대입 공격"""

    def __init__(self):
        self.tool_available = self._check_hydra()
        self.default_users = ["admin", "root", "administrator", "user", "azureuser"]
        self.default_passwords = [
            "password",
            "Password123",
            "123456",
            "admin",
            "P@ssw0rd",
        ]

    def _check_hydra(self) -> bool:
        """Hydra 설치 확인"""
        try:
            result = subprocess.run(
                ["hydra", "-h"], capture_output=True, timeout=5, text=True
            )
            # Hydra의 출력은 stdout과 stderr 모두 확인
            output = result.stdout + result.stderr
            return "Hydra" in output or "hydra" in output
        except:
            return False

    async def attack_ssh(
        self,
        target: str,
        username: Optional[str] = None,
        password_list: Optional[List[str]] = None,
        port: int = 22,
    ) -> AttackResult:
        """SSH 무차별 대입 공격"""
        logger.info(f"Hydra SSH 공격 시작: {target}:{port}")

        if not self.tool_available:
            logger.error("Hydra가 설치되지 않았습니다. 설치 후 다시 시도하세요.")
            return AttackResult(
                tool="hydra",
                target=f"{target}:{port}",
                success=False,
                findings=["Hydra not installed"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        try:
            # 사용자/비밀번호 목록 결정
            users = [username] if username else self.default_users
            passwords = password_list if password_list else self.default_passwords

            # 임시 사용자/비밀번호 파일 생성
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as user_file:
                user_file.write("\n".join(users))
                user_file_path = user_file.name

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as pass_file:
                pass_file.write("\n".join(passwords))
                pass_file_path = pass_file.name

            # Hydra 실행
            cmd = [
                "hydra",
                "-L",
                user_file_path,
                "-P",
                pass_file_path,
                "-t",
                "4",  # 4개 병렬 스레드
                "-vV",
                f"ssh://{target}:{port}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            findings = self._parse_hydra_output(result.stdout)

            # 임시 파일 삭제
            Path(user_file_path).unlink()
            Path(pass_file_path).unlink()

            return AttackResult(
                tool="hydra",
                target=f"{target}:{port}",
                success=any(
                    "valid credentials found:" in f.lower() for f in findings
                ),
                findings=findings,
                raw_output=result.stdout,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except Exception as e:
            logger.error(f"Hydra SSH 공격 실패: {e}")
            return AttackResult(
                tool="hydra",
                target=f"{target}:{port}",
                success=False,
                findings=[f"Attack failed: {str(e)}"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    def _parse_hydra_output(self, output: str) -> List[str]:
        """Hydra 출력 파싱"""
        findings = []

        for line in output.split("\n"):
            if "[22][ssh]" in line.lower() or "login:" in line.lower():
                # 성공한 자격 증명 찾기
                if "login:" in line and "password:" in line:
                    findings.append(f"Valid credentials found: {line.strip()}")

        return findings if findings else ["No valid credentials found"]


class SQLMapAttacker:
    """SQLMap SQL Injection 공격"""

    def __init__(self):
        self.tool_available = self._check_sqlmap()

    def _check_sqlmap(self) -> bool:
        """SQLMap 설치 확인"""
        try:
            result = subprocess.run(
                ["sqlmap", "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False

    async def attack(self, target_url: str) -> AttackResult:
        """SQL Injection 공격"""
        logger.info(f"SQLMap 공격 시작: {target_url}")

        if not self.tool_available:
            logger.error("SQLMap이 설치되지 않았습니다. 설치 후 다시 시도하세요.")
            return AttackResult(
                tool="sqlmap",
                target=target_url,
                success=False,
                findings=["SQLMap not installed"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        try:
            # SQLMap 실행: 기본 테스트
            cmd = [
                "sqlmap",
                "-u",
                target_url,
                "--batch",  # 자동 응답
                "--level=1",
                "--risk=1",
                "--threads=5",
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600  # 10분
            )

            findings = self._parse_sqlmap_output(result.stdout)

            return AttackResult(
                tool="sqlmap",
                target=target_url,
                success=len([f for f in findings if "vulnerable" in f.lower()]) > 0,
                findings=findings,
                raw_output=result.stdout,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except Exception as e:
            logger.error(f"SQLMap 공격 실패: {e}")
            return AttackResult(
                tool="sqlmap",
                target=target_url,
                success=False,
                findings=[f"Attack failed: {str(e)}"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    def _parse_sqlmap_output(self, output: str) -> List[str]:
        """SQLMap 출력 파싱"""
        findings = []

        for line in output.split("\n"):
            line_lower = line.lower()
            if "vulnerable" in line_lower or "injection" in line_lower:
                findings.append(line.strip())
            elif "parameter" in line_lower and "is" in line_lower:
                findings.append(line.strip())

        return findings if findings else ["No SQL injection vulnerabilities found"]


class MetasploitAttacker:
    """Metasploit 익스플로잇 프레임워크"""

    def __init__(self):
        self.tool_available = self._check_metasploit()

    def _check_metasploit(self) -> bool:
        """Metasploit 설치 확인"""
        try:
            result = subprocess.run(
                ["msfconsole", "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False

    async def exploit(
        self, target: str, exploit_module: str = "scanner/portscan/tcp"
    ) -> AttackResult:
        """익스플로잇 실행"""
        logger.info(f"Metasploit 익스플로잇 시작: {target}")

        if not self.tool_available:
            logger.error("Metasploit이 설치되지 않았습니다. 설치 후 다시 시도하세요.")
            return AttackResult(
                tool="metasploit",
                target=target,
                success=False,
                findings=["Metasploit not installed"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        # Metasploit은 복잡하므로 간단한 스캔만 수행
        try:
            # msfconsole 명령 스크립트 생성
            script = f"""
use {exploit_module}
set RHOSTS {target}
run
exit
"""
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".rc") as f:
                f.write(script)
                script_path = f.name

            cmd = ["msfconsole", "-q", "-r", script_path]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            Path(script_path).unlink()

            findings = self._parse_metasploit_output(result.stdout)

            return AttackResult(
                tool="metasploit",
                target=target,
                success=len(findings) > 0,
                findings=findings,
                raw_output=result.stdout,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except Exception as e:
            logger.error(f"Metasploit 익스플로잇 실패: {e}")
            return AttackResult(
                tool="metasploit",
                target=target,
                success=False,
                findings=[f"Exploit failed: {str(e)}"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    def _parse_metasploit_output(self, output: str) -> List[str]:
        """Metasploit 출력 파싱"""
        findings = []

        for line in output.split("\n"):
            line_lower = line.lower()
            if "session" in line_lower or "exploit" in line_lower:
                findings.append(line.strip())

        return findings if findings else ["Exploit unsuccessful or no results"]


class SQLServerAttacker:
    """SQL Server 무차별 대입 공격"""

    def __init__(self):
        self.tool_available = self._check_hydra()
        self.default_users = ["sa", "admin", "administrator", "user", "sqlserver"]
        self.default_passwords = [
            "password",
            "admin",
            "Admin123!",
            "Password123!",
            "YourStrong!Passw0rd",
            "sa",
            "123456",
        ]

    def _check_hydra(self) -> bool:
        """Hydra 설치 확인 (exit code가 아닌 출력 텍스트로 판단)"""
        try:
            result = subprocess.run(
                ["hydra", "-h"], capture_output=True, timeout=5, text=True
            )
            output = result.stdout + result.stderr
            return "Hydra" in output or "hydra" in output
        except:
            return False

    async def attack(self, target: str, port: int = 1433) -> AttackResult:
        """SQL Server 인증 무차별 대입 공격"""
        logger.info(f"SQL Server 공격 시작: {target}:{port}")

        if not self.tool_available:
            logger.error("Hydra가 설치되지 않았습니다. 설치 후 다시 시도하세요.")
            return AttackResult(
                tool="sqlserver",
                target=f"{target}:{port}",
                success=False,
                findings=["Hydra not installed"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        try:
            # 임시 사용자/비밀번호 파일 생성
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as user_file:
                user_file.write("\n".join(self.default_users))
                user_file_path = user_file.name

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as pass_file:
                pass_file.write("\n".join(self.default_passwords))
                pass_file_path = pass_file.name

            # Hydra 실행 (mssql 모듈)
            cmd = [
                "hydra",
                "-L",
                user_file_path,
                "-P",
                pass_file_path,
                "-t",
                "4",
                "-vV",
                f"mssql://{target}:{port}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            findings = self._parse_hydra_output(result.stdout)

            # 임시 파일 삭제
            Path(user_file_path).unlink()
            Path(pass_file_path).unlink()

            return AttackResult(
                tool="sqlserver",
                target=f"{target}:{port}",
                success=len(findings) > 0
                and any("valid" in f.lower() for f in findings),
                findings=findings,
                raw_output=result.stdout,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except Exception as e:
            logger.error(f"SQL Server 공격 실패: {e}")
            return AttackResult(
                tool="sqlserver",
                target=f"{target}:{port}",
                success=False,
                findings=[f"Attack failed: {str(e)}"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    def _parse_hydra_output(self, output: str) -> List[str]:
        """Hydra 출력 파싱"""
        findings = []

        for line in output.split("\n"):
            if "[1433][mssql]" in line.lower() or "login:" in line.lower():
                if "login:" in line and "password:" in line:
                    findings.append(f"Valid credentials found: {line.strip()}")

        return findings if findings else ["No valid credentials found"]


class RDPAttacker:
    """RDP 무차별 대입 공격"""

    def __init__(self):
        self.tool_available = self._check_hydra()
        self.default_users = ["administrator", "admin", "user", "guest"]
        self.default_passwords = [
            "password",
            "admin",
            "Admin123!",
            "Password123!",
            "123456",
            "Pa$$w0rd",
        ]

    def _check_hydra(self) -> bool:
        """Hydra 설치 확인 (exit code가 아닌 출력 텍스트로 판단)"""
        try:
            result = subprocess.run(
                ["hydra", "-h"], capture_output=True, timeout=5, text=True
            )
            output = result.stdout + result.stderr
            return "Hydra" in output or "hydra" in output
        except:
            return False

    async def attack(self, target: str, port: int = 3389) -> AttackResult:
        """RDP 무차별 대입 공격"""
        logger.info(f"RDP 공격 시작: {target}:{port}")

        if not self.tool_available:
            logger.error("Hydra가 설치되지 않았습니다. 설치 후 다시 시도하세요.")
            return AttackResult(
                tool="rdp",
                target=f"{target}:{port}",
                success=False,
                findings=["Hydra not installed"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        try:
            # 임시 사용자/비밀번호 파일 생성
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as user_file:
                user_file.write("\n".join(self.default_users))
                user_file_path = user_file.name

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as pass_file:
                pass_file.write("\n".join(self.default_passwords))
                pass_file_path = pass_file.name

            # Hydra 실행 (rdp 모듈)
            cmd = [
                "hydra",
                "-L",
                user_file_path,
                "-P",
                pass_file_path,
                "-t",
                "4",
                "-vV",
                f"rdp://{target}:{port}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            findings = self._parse_hydra_output(result.stdout)

            # 임시 파일 삭제
            Path(user_file_path).unlink()
            Path(pass_file_path).unlink()

            return AttackResult(
                tool="rdp",
                target=f"{target}:{port}",
                success=len(findings) > 0
                and any("valid" in f.lower() for f in findings),
                findings=findings,
                raw_output=result.stdout,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except Exception as e:
            logger.error(f"RDP 공격 실패: {e}")
            return AttackResult(
                tool="rdp",
                target=f"{target}:{port}",
                success=False,
                findings=[f"Attack failed: {str(e)}"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    def _parse_hydra_output(self, output: str) -> List[str]:
        """Hydra 출력 파싱"""
        findings = []

        for line in output.split("\n"):
            if "[3389][rdp]" in line.lower() or "login:" in line.lower():
                if "login:" in line and "password:" in line:
                    findings.append(f"Valid credentials found: {line.strip()}")

        return findings if findings else ["No valid credentials found"]


class StorageHTTPScanner:
    """스토리지 HTTP 엔드포인트 공개 접근 스캔 (로컬 Docker/Azure 호환)"""

    def __init__(self):
        self.requests_available = self._check_requests()

    def _check_requests(self) -> bool:
        """requests 라이브러리 확인"""
        try:
            import requests

            return True
        except ImportError:
            return False

    async def scan(self, target: str, port: int = 9000) -> AttackResult:
        """
        HTTP 스토리지 엔드포인트 스캔
        
        Args:
            target: IP 주소 또는 호스트명
            port: 포트 (MinIO=9000, Azurite=10000, Azure=443)
        """
        logger.info(f"스토리지 HTTP 엔드포인트 스캔 시작: {target}:{port}")

        if not self.requests_available:
            logger.error("requests 라이브러리가 설치되지 않았습니다.")
            return AttackResult(
                tool="storage_scan",
                target=f"{target}:{port}",
                success=False,
                findings=["requests library not installed"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        try:
            import requests

            findings = []
            base_url = f"http://{target}:{port}"

            # 1. 루트 엔드포인트 확인
            try:
                resp = requests.get(base_url, timeout=5)
                findings.append(f"✓ HTTP endpoint accessible: {resp.status_code}")
                
                if resp.status_code == 200:
                    findings.append("⚠️ Root endpoint returns 200 (possible misconfiguration)")
                    
                # HTTP 사용 경고 (HTTPS가 아닌 경우)
                if base_url.startswith("http://"):
                    findings.append("⚠️ Unencrypted HTTP traffic (security risk)")
                    
            except requests.exceptions.ConnectionError:
                findings.append("✗ Connection refused (service not running or port closed)")
                return AttackResult(
                    tool="storage_scan",
                    target=f"{target}:{port}",
                    success=False,
                    findings=findings,
                    raw_output="\n".join(findings),
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
            except requests.exceptions.Timeout:
                findings.append("✗ Connection timeout")
                return AttackResult(
                    tool="storage_scan",
                    target=f"{target}:{port}",
                    success=False,
                    findings=findings,
                    raw_output="\n".join(findings),
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                )

            # 2. 공개 버킷/컨테이너 스캔 시도 (MinIO/S3 스타일)
            common_buckets = ["public", "data", "backup", "uploads", "files", "test"]
            
            for bucket in common_buckets:
                try:
                    bucket_url = f"{base_url}/{bucket}"
                    resp = requests.get(bucket_url, timeout=3)
                    
                    if resp.status_code == 200:
                        findings.append(f"✓ Public bucket found: /{bucket} (HTTP 200)")
                        # XML 응답 확인 (S3/MinIO)
                        if "<?xml" in resp.text[:100]:
                            findings.append(f"  → Bucket listing accessible (XML response)")
                    elif resp.status_code == 403:
                        findings.append(f"  • Bucket exists but access denied: /{bucket}")
                    elif resp.status_code == 404:
                        pass  # 버킷 없음 (정상)
                        
                except:
                    pass  # 개별 버킷 스캔 실패는 무시

            # 3. MinIO API 엔드포인트 확인
            try:
                minio_health = f"{base_url}/minio/health/live"
                resp = requests.get(minio_health, timeout=3)
                if resp.status_code == 200:
                    findings.append("✓ MinIO server detected (health endpoint accessible)")
            except:
                pass

            # 4. 성공 여부 판단
            success = any(
                keyword in f.lower()
                for f in findings
                for keyword in ["public bucket found", "listing accessible", "200"]
            )

            return AttackResult(
                tool="storage_scan",
                target=f"{target}:{port}",
                success=success,
                findings=findings if findings else ["No vulnerabilities found"],
                raw_output="\n".join(findings),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        except Exception as e:
            logger.error(f"스토리지 스캔 실패: {e}")
            return AttackResult(
                tool="storage_scan",
                target=f"{target}:{port}",
                success=False,
                findings=[f"Scan failed: {str(e)}"],
                raw_output="",
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )


# ============================================================
# Phase 5: 공격 결과 분석
# ============================================================


class ResultAnalyzer:
    """공격 결과 분석"""

    def analyze(self, results: List[AttackResult]) -> Dict[str, Any]:
        """결과 분석"""
        logger.info("공격 결과 분석 시작")

        analysis = {
            "total_attacks": len(results),
            "successful_attacks": sum(1 for r in results if r.success),
            "by_tool": {},
            "critical_findings": [],
            "all_findings": [],
        }

        for result in results:
            # 도구별 집계
            if result.tool not in analysis["by_tool"]:
                analysis["by_tool"][result.tool] = {
                    "total": 0,
                    "successful": 0,
                    "findings": [],
                }

            analysis["by_tool"][result.tool]["total"] += 1
            if result.success:
                analysis["by_tool"][result.tool]["successful"] += 1

            analysis["by_tool"][result.tool]["findings"].extend(result.findings)

            # 중요 발견사항 수집
            for finding in result.findings:
                finding_lower = finding.lower()
                if any(
                    keyword in finding_lower
                    for keyword in [
                        "vulnerable",
                        "open",
                        "credentials",
                        "injection",
                        "exploit",
                    ]
                ):
                    analysis["critical_findings"].append(
                        {
                            "tool": result.tool,
                            "target": result.target,
                            "finding": finding,
                        }
                    )

            analysis["all_findings"].extend(result.findings)

        logger.info(
            f"분석 완료: {analysis['successful_attacks']}/{analysis['total_attacks']} 성공"
        )
        return analysis


class ReportGenerator:
    """최종 보고서 생성 (LLM 기반)"""

    def __init__(self):
        self.client: Optional[Any] = None
        self.session: Optional[Any] = None
        self.available = COPILOT_AVAILABLE

    async def initialize(self):
        """Copilot 클라이언트 초기화"""
        if not self.available:
            logger.warning("Copilot SDK 사용 불가, Static 보고서 생성")
            return

        try:
            logger.info("보고서 생성용 Copilot SDK 초기화 중...")
            self.client = CopilotClient()
            await self.client.start()
            self.session = await self.client.create_session({"model": "gpt-4.1"})
            logger.info("Copilot SDK 초기화 완료")
        except Exception as e:
            logger.error(f"Copilot SDK 초기화 실패: {e}")
            self.available = False

    async def generate(
        self,
        analysis: Dict[str, Any],
        deployment_info: DeploymentInfo,
        resources: List[BicepResource],
    ) -> str:
        """마크다운 보고서 생성 (LLM 기반)"""
        logger.info("보고서 생성 시작")

        # LLM을 사용하여 보고서 생성
        if self.available and self.session:
            try:
                report = await self._generate_with_llm(
                    analysis, deployment_info, resources
                )
                logger.info("LLM 기반 보고서 생성 완료")
                return report
            except Exception as e:
                logger.error(f"LLM 보고서 생성 실패: {e}, Static 보고서로 Fallback")

        # Fallback: Static 보고서
        return self._generate_static_report(analysis, deployment_info, resources)

    async def _generate_with_llm(
        self,
        analysis: Dict[str, Any],
        deployment_info: DeploymentInfo,
        resources: List[BicepResource],
    ) -> str:
        """LLM을 사용한 동적 보고서 생성"""
        prompt = self._build_report_prompt(analysis, deployment_info, resources)
        response = await self.session.send_and_wait({"prompt": prompt}, timeout=180.0)
        return response.data.content

    def _build_report_prompt(
        self,
        analysis: Dict[str, Any],
        deployment_info: DeploymentInfo,
        resources: List[BicepResource],
    ) -> str:
        """보고서 생성 프롬프트 구성"""

        # 컨테이너 정보 요약
        containers_summary = "\n".join(
            [
                f"- {c['name']}: {c['image']} (IP: {c['ip']}, Status: {c['status']})"
                for c in deployment_info.containers
            ]
        )

        # 공격 결과 요약
        attack_summary = f"""
총 공격: {analysis['total_attacks']}회
성공: {analysis['successful_attacks']}회
실패: {analysis['total_attacks'] - analysis['successful_attacks']}회
"""

        # 도구별 결과
        tools_summary = "\n".join(
            [
                f"- {tool}: {stats['total']}회 실행, {stats['successful']}회 성공, {len(stats['findings'])}개 발견"
                for tool, stats in analysis["by_tool"].items()
            ]
        )

        # 중요 발견사항
        findings_summary = (
            "\n".join(
                [
                    f"{i+1}. [{f['tool']}] {f['target']}: {f['finding']}"
                    for i, f in enumerate(analysis["critical_findings"])
                ]
            )
            if analysis["critical_findings"]
            else "중요 발견사항 없음"
        )

        prompt = f"""당신은 보안 전문가입니다. 아래 정보를 바탕으로 **한국어**로 침투 테스트 보고서를 작성하세요.

## 제공된 정보

### 배포 환경
- 총 리소스: {len(resources)}개
- 배포된 컨테이너: {len(deployment_info.containers)}개
- 네트워크: {', '.join(deployment_info.networks)}

#### 컨테이너 목록
{containers_summary}

### 공격 실행 결과
{attack_summary}

#### 도구별 결과
{tools_summary}

### 중요 발견사항
{findings_summary}

## 보고서 작성 지침

다음 포맷을 **반드시 준수**하여 마크다운 형식으로 작성하세요:

```markdown
# 로컬 환경 침투 테스트 보고서

**생성 시각**: {time.strftime('%Y-%m-%d %H:%M:%S')}

## 1. 경영진 요약

(공격 결과를 비즈니스 관점에서 요약. 총 공격 수, 성공 횟수, 중요 발견사항 개수를 포함하고, 
전반적인 보안 상태를 평가하세요. 2-3문단으로 작성.)

## 2. 배포 환경

- **총 리소스**: {len(resources)}개
- **배포된 컨테이너**: {len(deployment_info.containers)}개
- **네트워크**: {', '.join(deployment_info.networks)}

### 컨테이너 목록

| 이름 | 이미지 | IP 주소 | 상태 |
|------|--------|---------|------|
(각 컨테이너 정보를 테이블로 작성)

## 3. 공격 결과

- **총 공격 횟수**: {analysis['total_attacks']}
- **성공한 공격**: {analysis['successful_attacks']}
- **실패한 공격**: {analysis['total_attacks'] - analysis['successful_attacks']}

### 도구별 결과

(각 도구별로 실행 횟수, 성공 횟수, 발견사항을 상세히 설명)

## 4. 중요 발견사항

(각 발견사항을 번호를 매겨 상세히 설명. 취약점의 심각도, 영향도, 악용 가능성을 포함)

## 5. 권장사항

### 즉시 조치 필요

(발견된 취약점을 기반으로 즉시 조치가 필요한 사항을 체크박스 리스트로 작성)

### 단기 조치 (1-2주)

(단기적으로 개선이 필요한 사항을 체크박스 리스트로 작성)

### 중기 조치 (1개월)

(중기적으로 개선이 필요한 사항을 체크박스 리스트로 작성)

## 6. 결론

(전체 테스트 결과를 종합하여 2-3문단으로 요약. 주요 위협 요소와 전반적인 보안 개선 방향을 제시)

---
*Report generated by LocalAttackAgent v1.0 (LLM-powered)*
```

## 중요 사항
1. **반드시 한국어로 작성**하세요.
2. 위 포맷을 정확히 따르세요.
3. 제공된 데이터를 **분석하고 해석**하여 의미있는 인사이트를 제공하세요.
4. 발견된 취약점에 대한 **구체적이고 실행 가능한 권장사항**을 제시하세요.
5. 기술적 용어는 필요시 간단한 설명을 추가하세요.
6. 마크다운 형식을 올바르게 사용하세요.

보고서를 작성해주세요:"""

        return prompt

    def _generate_static_report(
        self,
        analysis: Dict[str, Any],
        deployment_info: DeploymentInfo,
        resources: List[BicepResource],
    ) -> str:
        """정적 보고서 생성 (Fallback)"""
        logger.info("정적 보고서 생성 중...")

        lines = [
            "# 로컬 환경 침투 테스트 보고서",
            "",
            f"**생성 시각**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 1. 경영진 요약",
            "",
            f"본 침투 테스트에서 총 **{analysis['total_attacks']}개의 공격**을 수행하였으며, ",
            f"이 중 **{analysis['successful_attacks']}개가 성공**하였습니다. ",
            f"**{len(analysis['critical_findings'])}개의 중요 발견사항**이 확인되었습니다.",
            "",
            "## 2. 배포 환경",
            "",
            f"- **총 리소스**: {len(resources)}개",
            f"- **배포된 컨테이너**: {len(deployment_info.containers)}개",
            f"- **네트워크**: {', '.join(deployment_info.networks)}",
            "",
            "### 컨테이너 목록",
            "",
            "| 이름 | 이미지 | IP 주소 | 상태 |",
            "|------|--------|---------|------|",
        ]

        for container in deployment_info.containers:
            lines.append(
                f"| {container['name']} | {container['image']} | "
                f"{container['ip']} | {container['status']} |"
            )

        lines += [
            "",
            "## 3. 공격 결과",
            "",
            f"- **총 공격 횟수**: {analysis['total_attacks']}",
            f"- **성공한 공격**: {analysis['successful_attacks']}",
            f"- **실패한 공격**: {analysis['total_attacks'] - analysis['successful_attacks']}",
            "",
            "### 도구별 결과",
            "",
        ]

        for tool, stats in analysis["by_tool"].items():
            lines.append(f"#### {tool.upper()}")
            lines.append(f"- 실행 횟수: {stats['total']}")
            lines.append(f"- 성공 횟수: {stats['successful']}")
            lines.append(f"- 발견사항: {len(stats['findings'])}개")
            lines.append("")

        lines += [
            "## 4. 중요 발견사항",
            "",
        ]

        if analysis["critical_findings"]:
            for i, finding in enumerate(analysis["critical_findings"], 1):
                lines.append(f"### {i}. [{finding['tool']}] {finding['target']}")
                lines.append(f"```\n{finding['finding']}\n```")
                lines.append("")
        else:
            lines.append("중요 발견사항 없음")
            lines.append("")

        lines += [
            "## 5. 권장사항",
            "",
            "### 즉시 조치 필요",
            "",
            "- [ ] SSH 포트(22)를 특정 IP 대역으로 제한",
            "- [ ] RDP 포트(3389)를 VPN 또는 Bastion을 통해서만 접근",
            "- [ ] SQL Server 방화벽을 애플리케이션 서브넷으로 제한",
            "- [ ] 스토리지 계정 HTTPS 전용 설정 활성화",
            "",
            "### 단기 조치 (1-2주)",
            "",
            "- [ ] Key Vault 네트워크 ACL 설정",
            "- [ ] App Service HTTPS 전용 설정",
            "- [ ] VM 디스크 암호화 활성화",
            "",
            "### 중기 조치 (1개월)",
            "",
            "- [ ] Azure AD 인증 통합",
            "- [ ] 로그 모니터링 및 알림 설정",
            "- [ ] 정기적인 보안 스캔 자동화",
            "",
            "## 6. 결론",
            "",
            "본 침투 테스트를 통해 로컬 환경에서 실제 공격을 시뮬레이션하였으며, ",
            "다수의 보안 취약점이 확인되었습니다. 특히 네트워크 보안 그룹의 과도한 ",
            "허용 규칙과 인증 메커니즘의 약점이 주요 위협 요소로 식별되었습니다.",
            "",
            "---",
            f"*Report generated by LocalAttackAgent v1.0 (Static)*",
        ]

        report = "\n".join(lines)
        logger.info("정적 보고서 생성 완료")
        return report

    async def cleanup(self):
        """Copilot 세션 종료"""
        if self.client:
            await self.client.stop()

    # ============================================================
    # 메인 Agent 클래스 (업데이트)
    # ============================================================


# ============================================================
# 실행 헬퍼
# ============================================================


async def run_agent(bicep_input: str, use_docker: bool = False) -> Dict[str, Any]:
    """
    Local Attack Agent 실행

    Args:
        bicep_input: Bicep 파일 경로 또는 Bicep 코드 문자열
        use_docker: Docker 사용 여부
    """
    agent = LocalAttackAgent(use_docker=use_docker)

    try:
        # 입력이 파일 경로인지 Bicep 코드인지 판단
        bicep_code = None

        # 1. 파일 경로인지 확인 (.bicep 확장자 또는 파일 존재)
        if bicep_input.endswith(".bicep") or Path(bicep_input).exists():
            logger.info(f"Bicep 파일에서 코드 읽기: {bicep_input}")
            try:
                with open(bicep_input, "r", encoding="utf-8") as f:
                    bicep_code = f.read()
            except Exception as e:
                logger.error(f"파일 읽기 실패: {e}")
                raise
        else:
            # 2. Bicep 코드 문자열로 간주 (resource, param, var 등 키워드 확인)
            if any(
                keyword in bicep_input
                for keyword in ["resource", "param", "var", "module", "output"]
            ):
                logger.info("Bicep 코드 문자열로 처리")
                bicep_code = bicep_input
            else:
                # 3. 파일이 존재하지 않는 경로로 간주하고 에러
                logger.error(
                    f"유효하지 않은 입력: '{bicep_input}'는 파일 경로가 아니며 Bicep 코드도 아닙니다."
                )
                raise ValueError(
                    f"Invalid input: '{bicep_input}' is neither a valid file path nor Bicep code"
                )

        # 분석 및 공격
        result = await agent.analyze_and_attack(bicep_code)

        # 컨테이너 정리
        logger.info("\n" + "=" * 60)
        agent.cleanup()
        logger.info("=" * 60)

        return result

    except Exception as e:
        # 에러 발생 시에도 정리
        logger.error(f"에이전트 실행 중 오류: {e}")
        try:
            agent.cleanup()
        except:
            pass
        raise


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 샘플 실행
    import sys

    if len(sys.argv) > 1:
        bicep_input = sys.argv[1]
    else:
        bicep_input = "samples/sample_bicep.bicep"

    # Docker 필수 체크
    try:
        import docker

        client = docker.from_env()
        client.ping()
        print("✅ Docker 연결 성공!")
        print("⚠️  첫 실행 시 이미지 다운로드에 5-10분 소요될 수 있습니다.")
        print()
    except Exception as e:
        print(f"❌ Docker 연결 실패: {e}")
        print("→ Docker를 시작한 후 다시 시도하세요.")
        sys.exit(1)

    print(f"\n{'='*60}")
    # 파일 경로인지 코드인지 표시
    if bicep_input.endswith(".bicep") or Path(bicep_input).exists():
        print(f"Bicep 파일: {bicep_input}")
    else:
        print(
            f"Bicep 코드: {bicep_input[:50]}..."
            if len(bicep_input) > 50
            else f"Bicep 코드: {bicep_input}"
        )
    print(f"배포 모드: Docker (실제 컨테이너)")
    print(f"{'='*60}\n")

    result = asyncio.run(run_agent(bicep_input, use_docker=True))

    print(f"\n{'='*60}")
    print("실행 결과:")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
