"""
RedTeam Agent (Mock 구현).

추후 Microsoft Agent Framework (Semantic Kernel) + GitHub Copilot SDK로 교체 예정.
현재는 샘플 BiCep 코드에 대한 정적 분석 결과를 반환합니다.

---
Github Copilot SDK 예시 코드 (https://github.com/github/copilot-sdk/blob/main/python/README.md)
```
import asyncio
from copilot import CopilotClient

async def main():
    client = CopilotClient()
    await client.start()

    session = await client.create_session({"model": "gpt-4.1"})
    response = await session.send_and_wait({"prompt": "What is 2 + 2?"})

    print(response.data.content)

    await client.stop()

asyncio.run(main())
```
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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
    target_vulnerabilities: list[str]
    severity: str
    prerequisites: str
    attack_chain: list[str]
    expected_impact: str
    detection_difficulty: str
    likelihood: str


@dataclass
class AnalysisResult:
    """RedTeam 분석 전체 결과."""

    architecture_summary: dict
    vulnerabilities: list[VulnerabilityItem]
    attack_scenarios: list[AttackScenario]
    report: str
    raw_results: dict = field(default_factory=dict)

    @property
    def vulnerability_count(self) -> dict:
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for v in self.vulnerabilities:
            counts[v.severity] = counts.get(v.severity, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# 정적 규칙 기반 취약점 탐지 (Mock)
# ---------------------------------------------------------------------------

_RULES: list[dict] = [
    {
        "pattern": r"sourceAddressPrefix:\s*'\*'",
        "id_suffix": "NET",
        "severity": "Critical",
        "category": "Network",
        "title": "NSG 규칙에서 모든 소스 IP(*) 허용",
        "description": "네트워크 보안 그룹 인바운드 규칙이 모든 IP 주소(*)에서의 접근을 허용하고 있습니다. 이는 무차별 대입 공격 및 비인가 접근의 위험을 높입니다.",
        "remediation": "sourceAddressPrefix를 특정 IP 대역(예: '10.0.0.0/8')으로 제한하세요.",
        "benchmark_ref": "CIS 6.1 / ASB NS-1",
    },
    {
        "pattern": r"destinationPortRange:\s*'22'[\s\S]*?sourceAddressPrefix:\s*'\*'",
        "id_suffix": "SSH",
        "severity": "Critical",
        "category": "Network",
        "title": "SSH(22) 포트가 모든 IP에 개방",
        "description": "SSH 포트(22)가 인터넷 전체에 공개되어 있어 무차별 대입 공격에 노출됩니다.",
        "remediation": "SSH 접근을 관리자 IP 대역 또는 Azure Bastion을 통해서만 허용하세요.",
        "benchmark_ref": "CIS 6.2 / ASB NS-1",
    },
    {
        "pattern": r"destinationPortRange:\s*'3389'[\s\S]*?sourceAddressPrefix:\s*'\*'",
        "id_suffix": "RDP",
        "severity": "Critical",
        "category": "Network",
        "title": "RDP(3389) 포트가 모든 IP에 개방",
        "description": "RDP 포트(3389)가 인터넷 전체에 공개되어 있어 원격 데스크톱 무차별 대입 공격에 노출됩니다.",
        "remediation": "RDP 접근을 Azure Bastion 또는 VPN을 통해서만 허용하세요.",
        "benchmark_ref": "CIS 6.2 / ASB NS-1",
    },
    {
        "pattern": r"supportsHttpsTrafficOnly:\s*false",
        "id_suffix": "HTTP",
        "severity": "High",
        "category": "Encryption",
        "title": "스토리지 계정에서 HTTP 트래픽 허용",
        "description": "스토리지 계정이 암호화되지 않은 HTTP 트래픽을 허용하여 데이터 유출 위험이 있습니다.",
        "remediation": "supportsHttpsTrafficOnly: true로 설정하세요.",
        "benchmark_ref": "CIS 3.1 / ASB DP-3",
    },
    {
        "pattern": r"allowBlobPublicAccess:\s*true",
        "id_suffix": "BLOB",
        "severity": "High",
        "category": "DataProtection",
        "title": "Blob 공개 접근 허용",
        "description": "스토리지 계정의 Blob 컨테이너가 공개 접근을 허용하여 데이터 유출 위험이 있습니다.",
        "remediation": "allowBlobPublicAccess: false로 설정하세요.",
        "benchmark_ref": "CIS 3.5 / ASB DP-1",
    },
    {
        "pattern": r"startIpAddress:\s*'0\.0\.0\.0'[\s\S]*?endIpAddress:\s*'255\.255\.255\.255'",
        "id_suffix": "SQLFW",
        "severity": "Critical",
        "category": "Network",
        "title": "SQL Server 방화벽에서 모든 IP 허용",
        "description": "SQL Server 방화벽 규칙이 전체 IP 대역(0.0.0.0 ~ 255.255.255.255)을 허용하여 데이터베이스가 인터넷에 완전히 노출됩니다.",
        "remediation": "방화벽 규칙을 애플리케이션 서브넷의 IP 대역으로 제한하세요.",
        "benchmark_ref": "CIS 4.1.2 / ASB NS-1",
    },
    {
        "pattern": r"ftpsState:\s*'AllAllowed'",
        "id_suffix": "FTP",
        "severity": "High",
        "category": "Encryption",
        "title": "App Service에서 FTP 허용",
        "description": "App Service에서 암호화되지 않은 FTP 배포가 허용되어 자격 증명 및 소스 코드 유출 위험이 있습니다.",
        "remediation": "ftpsState: 'FtpsOnly' 또는 'Disabled'로 설정하세요.",
        "benchmark_ref": "CIS 9.10 / ASB DP-3",
    },
    {
        "pattern": r"enableSoftDelete:\s*false",
        "id_suffix": "KV-SD",
        "severity": "High",
        "category": "Configuration",
        "title": "Key Vault 소프트 삭제 비활성화",
        "description": "Key Vault의 소프트 삭제가 비활성화되어 실수로 삭제된 비밀 키를 복구할 수 없습니다.",
        "remediation": "enableSoftDelete: true로 설정하세요.",
        "benchmark_ref": "CIS 8.4 / ASB DP-6",
    },
    {
        "pattern": r"enablePurgeProtection:\s*false",
        "id_suffix": "KV-PP",
        "severity": "Medium",
        "category": "Configuration",
        "title": "Key Vault 퍼지 보호 비활성화",
        "description": "Key Vault의 퍼지 보호가 비활성화되어 악의적인 영구 삭제가 가능합니다.",
        "remediation": "enablePurgeProtection: true로 설정하세요.",
        "benchmark_ref": "CIS 8.4 / ASB DP-6",
    },
    {
        "pattern": r"defaultAction:\s*'Allow'",
        "id_suffix": "KV-NET",
        "severity": "High",
        "category": "Network",
        "title": "Key Vault 네트워크 제한 없음",
        "description": "Key Vault의 네트워크 ACL 기본 동작이 'Allow'로 설정되어 모든 네트워크에서 접근 가능합니다.",
        "remediation": "defaultAction: 'Deny'로 변경하고 허용 IP/서브넷을 명시하세요.",
        "benchmark_ref": "CIS 8.6 / ASB NS-1",
    },
    {
        "pattern": r"adminPassword",
        "id_suffix": "PWD",
        "severity": "Medium",
        "category": "Identity",
        "title": "VM 비밀번호 인증 사용",
        "description": "가상 머신이 비밀번호 기반 인증을 사용하고 있습니다. SSH 키 인증이 더 안전합니다.",
        "remediation": "SSH 키 기반 인증으로 전환하고 disablePasswordAuthentication: true를 설정하세요.",
        "benchmark_ref": "CIS 7.10 / ASB IM-1",
    },
    {
        "pattern": r"publicIPAddress",
        "id_suffix": "PIP",
        "severity": "Medium",
        "category": "Network",
        "title": "VM에 공용 IP 직접 연결",
        "description": "가상 머신에 공용 IP가 직접 연결되어 인터넷에 노출됩니다. Azure Bastion 또는 Load Balancer 사용을 권장합니다.",
        "remediation": "공용 IP를 제거하고 Azure Bastion 또는 Application Gateway를 사용하세요.",
        "benchmark_ref": "ASB NS-1",
    },
]

_ATTACK_TEMPLATES: list[dict] = [
    {
        "name": "SSH 무차별 대입 공격을 통한 서버 장악",
        "mitre_technique": "T1110 - Brute Force",
        "vuln_categories": ["SSH", "NET"],
        "severity": "Critical",
        "prerequisites": "인터넷 접근 가능한 공격자, SSH 클라이언트",
        "attack_chain": [
            "1단계: 공개된 공용 IP 주소 스캐닝 (Shodan, Censys 등)",
            "2단계: SSH 포트(22) 오픈 확인",
            "3단계: Hydra/Medusa 등으로 SSH 무차별 대입 공격 수행",
            "4단계: 유효 자격 증명 획득 후 서버 접속",
            "5단계: 내부 네트워크 피벗팅 및 추가 리소스 접근",
        ],
        "expected_impact": "서버 완전 장악, 내부 네트워크 접근, 데이터 유출",
        "detection_difficulty": "Medium",
        "likelihood": "High",
    },
    {
        "name": "SQL Server 직접 접근을 통한 데이터 탈취",
        "mitre_technique": "T1190 - Exploit Public-Facing Application",
        "vuln_categories": ["SQLFW"],
        "severity": "Critical",
        "prerequisites": "SQL 클라이언트, 인터넷 접근",
        "attack_chain": [
            "1단계: SQL Server 엔드포인트 발견 (포트 1433 스캔)",
            "2단계: 방화벽 우회 불필요 (전체 IP 허용됨)",
            "3단계: SQL 인증 무차별 대입 또는 기본 자격 증명 시도",
            "4단계: 데이터베이스 접근 및 데이터 덤프",
            "5단계: 민감 데이터 외부 유출",
        ],
        "expected_impact": "전체 데이터베이스 탈취, 개인정보 유출, 규정 위반",
        "detection_difficulty": "Medium",
        "likelihood": "High",
    },
    {
        "name": "스토리지 계정 공개 Blob을 통한 정보 수집",
        "mitre_technique": "T1530 - Data from Cloud Storage Object",
        "vuln_categories": ["BLOB", "HTTP"],
        "severity": "High",
        "prerequisites": "웹 브라우저 또는 Azure Storage Explorer",
        "attack_chain": [
            "1단계: 스토리지 계정 이름 추측 또는 DNS 열거",
            "2단계: 공개 Blob 컨테이너 목록 조회",
            "3단계: HTTP를 통한 비암호화 데이터 다운로드",
            "4단계: 민감 데이터(설정 파일, 백업 등) 수집",
        ],
        "expected_impact": "설정 파일, 자격 증명, 백업 데이터 유출",
        "detection_difficulty": "Hard",
        "likelihood": "High",
    },
    {
        "name": "Key Vault 비밀 키 탈취 및 인프라 장악",
        "mitre_technique": "T1552 - Unsecured Credentials",
        "vuln_categories": ["KV-NET", "KV-SD"],
        "severity": "Critical",
        "prerequisites": "Azure 인증 토큰 (서비스 프린시플 또는 관리 ID 탈취)",
        "attack_chain": [
            "1단계: 탈취한 자격 증명으로 Azure 인증",
            "2단계: Key Vault 네트워크 제한 없어 어디서든 접근 가능",
            "3단계: Key Vault에서 비밀 키, 인증서 목록 조회",
            "4단계: 데이터베이스 연결 문자열, API 키 등 탈취",
            "5단계: 탈취한 자격 증명으로 추가 리소스 접근 및 데이터 유출",
        ],
        "expected_impact": "전체 인프라 자격 증명 탈취, 연쇄적 침해",
        "detection_difficulty": "Hard",
        "likelihood": "Medium",
    },
]


class RedTeamAgent:
    """
    Azure 아키텍처 보안 검증 RedTeam 에이전트 (Mock).

    추후 Semantic Kernel + GitHub Copilot SDK로 교체 예정.
    현재는 정적 규칙 기반 분석을 수행합니다.
    """

    async def analyze(self, bicep_code: str) -> AnalysisResult:
        logger.info("RedTeam 보안 분석 시작 (mock)")

        # Step 1: 아키텍처 분석
        await asyncio.sleep(0.3)
        architecture = self._analyze_architecture(bicep_code)

        # Step 2: 취약점 탐지
        await asyncio.sleep(0.3)
        vulnerabilities = self._detect_vulnerabilities(bicep_code)

        # Step 3: 공격 시뮬레이션
        await asyncio.sleep(0.3)
        attacks = self._simulate_attacks(vulnerabilities)

        # Step 4: 보고서 생성
        report = self._generate_report(architecture, vulnerabilities, attacks)

        logger.info(
            "RedTeam 분석 완료: 취약점 %d개, 공격 시나리오 %d개",
            len(vulnerabilities),
            len(attacks),
        )

        return AnalysisResult(
            architecture_summary=architecture,
            vulnerabilities=vulnerabilities,
            attack_scenarios=attacks,
            report=report,
            raw_results={
                "model": "mock-static-rules",
                "vulnerability_count": {
                    "total": len(vulnerabilities),
                    **{
                        sev: sum(1 for v in vulnerabilities if v.severity == sev)
                        for sev in ["Critical", "High", "Medium", "Low"]
                    },
                },
                "attack_scenario_count": len(attacks),
            },
        )

    # ------------------------------------------------------------------
    # 내부 분석 단계
    # ------------------------------------------------------------------

    def _analyze_architecture(self, bicep_code: str) -> dict:
        resources = []
        for m in re.finditer(r"resource\s+(\w+)\s+'([^']+)'", bicep_code):
            resources.append({"name": m.group(1), "type": m.group(2)})

        return {
            "resources": resources,
            "resource_count": len(resources),
        }

    def _detect_vulnerabilities(self, bicep_code: str) -> list[VulnerabilityItem]:
        vulns = []
        idx = 1
        for rule in _RULES:
            if re.search(rule["pattern"], bicep_code):
                vulns.append(
                    VulnerabilityItem(
                        id=f"VULN-{idx:03d}",
                        severity=rule["severity"],
                        category=rule["category"],
                        affected_resource=rule["id_suffix"],
                        title=rule["title"],
                        description=rule["description"],
                        evidence=rule["pattern"],
                        remediation=rule["remediation"],
                        benchmark_ref=rule.get("benchmark_ref", ""),
                    )
                )
                idx += 1
        return vulns

    def _simulate_attacks(
        self, vulnerabilities: list[VulnerabilityItem]
    ) -> list[AttackScenario]:
        found_suffixes = {v.affected_resource for v in vulnerabilities}
        scenarios = []
        idx = 1
        for tpl in _ATTACK_TEMPLATES:
            if any(cat in found_suffixes for cat in tpl["vuln_categories"]):
                matched_vulns = [
                    v.id
                    for v in vulnerabilities
                    if v.affected_resource in tpl["vuln_categories"]
                ]
                scenarios.append(
                    AttackScenario(
                        id=f"ATK-{idx:03d}",
                        name=tpl["name"],
                        mitre_technique=tpl["mitre_technique"],
                        target_vulnerabilities=matched_vulns,
                        severity=tpl["severity"],
                        prerequisites=tpl["prerequisites"],
                        attack_chain=tpl["attack_chain"],
                        expected_impact=tpl["expected_impact"],
                        detection_difficulty=tpl["detection_difficulty"],
                        likelihood=tpl["likelihood"],
                    )
                )
                idx += 1
        return scenarios

    def _generate_report(
        self,
        architecture: dict,
        vulnerabilities: list[VulnerabilityItem],
        attacks: list[AttackScenario],
    ) -> str:
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for v in vulnerabilities:
            counts[v.severity] = counts.get(v.severity, 0) + 1

        lines = [
            "# Azure 아키텍처 보안 평가 보고서",
            "",
            "## 1. 경영진 요약",
            "",
            f"본 보안 평가에서 총 **{len(vulnerabilities)}개의 취약점**이 발견되었으며, "
            f"이 중 **{counts['Critical']}개가 심각(Critical)**, **{counts['High']}개가 높음(High)** 등급입니다. "
            f"**{len(attacks)}개의 공격 시나리오**가 도출되었으며, 즉각적인 보안 조치가 필요합니다.",
            "",
            "## 2. 아키텍처 개요",
            "",
            f"분석 대상: {architecture['resource_count']}개 Azure 리소스",
            "",
            "| 리소스 이름 | 리소스 유형 |",
            "|---|---|",
        ]
        for r in architecture["resources"]:
            lines.append(f"| {r['name']} | `{r['type']}` |")

        lines += [
            "",
            "## 3. 취약점 평가",
            "",
            "| ID | 심각도 | 카테고리 | 제목 |",
            "|---|---|---|---|",
        ]
        for v in sorted(
            vulnerabilities,
            key=lambda x: ["Critical", "High", "Medium", "Low"].index(x.severity),
        ):
            lines.append(f"| {v.id} | **{v.severity}** | {v.category} | {v.title} |")

        lines.append("")
        for v in vulnerabilities:
            lines += [
                f"### {v.id}: {v.title}",
                "",
                f"- **심각도**: {v.severity}",
                f"- **카테고리**: {v.category}",
                f"- **설명**: {v.description}",
                f"- **수정 방법**: {v.remediation}",
                f"- **벤치마크**: {v.benchmark_ref}",
                "",
            ]

        lines += [
            "## 4. 공격 시뮬레이션 결과",
            "",
        ]
        for atk in attacks:
            lines += [
                f"### {atk.id}: {atk.name}",
                "",
                f"- **MITRE ATT&CK**: {atk.mitre_technique}",
                f"- **심각도**: {atk.severity}",
                f"- **탐지 난이도**: {atk.detection_difficulty}",
                f"- **발생 가능성**: {atk.likelihood}",
                f"- **전제 조건**: {atk.prerequisites}",
                "",
                "**공격 체인:**",
                "",
            ]
            for step in atk.attack_chain:
                lines.append(f"  {step}")
            lines += [
                "",
                f"**예상 피해:** {atk.expected_impact}",
                "",
            ]

        lines += [
            "## 5. 개선 로드맵",
            "",
            "### 즉시 조치 (Critical/High)",
            "",
        ]
        for v in vulnerabilities:
            if v.severity in ("Critical", "High"):
                lines.append(f"- [ ] **{v.id}** {v.title}: {v.remediation}")
        lines += [
            "",
            "### 단기 조치 (Medium, 1-2주)",
            "",
        ]
        for v in vulnerabilities:
            if v.severity == "Medium":
                lines.append(f"- [ ] **{v.id}** {v.title}: {v.remediation}")
        lines += [
            "",
            "### 중기 조치 (Low, 1개월)",
            "",
        ]
        for v in vulnerabilities:
            if v.severity == "Low":
                lines.append(f"- [ ] **{v.id}** {v.title}: {v.remediation}")

        lines += [
            "",
            "## 6. 결론",
            "",
            f"본 평가에서 {len(vulnerabilities)}개의 보안 취약점과 "
            f"{len(attacks)}개의 실질적 공격 시나리오가 확인되었습니다. "
            "특히 네트워크 보안 그룹의 과도한 허용 규칙과 데이터 저장소의 공개 접근 설정은 "
            "즉각적인 조치가 필요합니다.",
        ]

        return "\n".join(lines)
