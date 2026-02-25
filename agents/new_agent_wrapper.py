"""
Agent Wrapper: new_agent.py와 new_agent_with_tools.py를 API와 호환되도록 감싸는 Wrapper

두 가지 Agent 모드 지원:
- "zero-tools": 완전 자율 Agent (느리지만 창의적)
- "with-tools": 도구 함수 사용 Agent (빠르고 일관적)
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Literal

from agents.agent import AnalysisResult, VulnerabilityItem, AttackScenario
from agents.new_agent import convert_and_attack as zero_tools_convert_and_attack
from agents.new_agent_with_tools import convert_bicep_to_compose as with_tools_convert

logger = logging.getLogger(__name__)

AgentMode = Literal["zero-tools", "with-tools"]


# ============================================================
# JSON Parser
# ============================================================


def extract_json_from_text(text: str) -> Optional[dict]:
    """
    텍스트에서 JSON 코드 블록을 추출합니다.
    
    Agent가 ```json ... ``` 형식으로 출력한 JSON을 찾습니다.
    """
    # JSON 코드 블록 찾기: ```json ... ```
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not matches:
        # 코드 블록 없이 JSON만 있는 경우
        json_pattern = r'\{[\s\S]*"vulnerabilities"[\s\S]*\}'
        matches = re.findall(json_pattern, text)
    
    if not matches:
        logger.warning("No JSON block found in Agent output")
        return None
    
    # 가장 큰 JSON 블록 선택 (가장 완전한 것일 가능성 높음)
    json_str = max(matches, key=len)
    
    try:
        data = json.loads(json_str)
        logger.info(f"✅ Successfully parsed JSON with {len(data.get('vulnerabilities', []))} vulnerabilities")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing failed: {e}")
        return None


def parse_json_to_analysis_result(json_data: dict, bicep_code: str) -> AnalysisResult:
    """
    JSON 데이터를 AnalysisResult로 변환합니다.
    """
    # Vulnerabilities 변환
    vulnerabilities = []
    for v in json_data.get("vulnerabilities", []):
        try:
            vuln = VulnerabilityItem(
                id=v.get("id", "UNKNOWN"),
                severity=v.get("severity", "Medium"),
                category=v.get("category", "Unknown"),
                affected_resource=v.get("affected_resource", "Unknown"),
                title=v.get("title", "Unknown vulnerability"),
                description=v.get("description", ""),
                evidence=v.get("evidence", ""),
                remediation=v.get("remediation", ""),
                benchmark_ref=v.get("benchmark_ref", ""),
            )
            vulnerabilities.append(vuln)
        except Exception as e:
            logger.warning(f"Failed to parse vulnerability {v.get('id')}: {e}")
    
    # Attack Scenarios 변환
    attack_scenarios = []
    for a in json_data.get("attack_scenarios", []):
        try:
            scenario = AttackScenario(
                id=a.get("id", "UNKNOWN"),
                name=a.get("name", "Unknown attack"),
                mitre_technique=a.get("mitre_technique", ""),
                target_vulnerabilities=a.get("target_vulnerabilities", []),
                severity=a.get("severity", "Medium"),
                prerequisites=a.get("prerequisites", ""),
                attack_chain=a.get("attack_chain", []),
                expected_impact=a.get("expected_impact", ""),
                detection_difficulty=a.get("detection_difficulty", "Medium"),
                likelihood=a.get("likelihood", "Medium"),
            )
            attack_scenarios.append(scenario)
        except Exception as e:
            logger.warning(f"Failed to parse attack scenario {a.get('id')}: {e}")
    
    # Architecture summary (간단하게)
    architecture_summary = {
        "bicep_length": len(bicep_code),
        "resource_count": len(vulnerabilities),  # 근사치
    }
    
    # Report는 Markdown 파일에서 읽기
    report = ""
    try:
        if Path("red_team_security_report.md").exists():
            report = Path("red_team_security_report.md").read_text()
    except Exception as e:
        logger.warning(f"Failed to read markdown report: {e}")
    
    return AnalysisResult(
        architecture_summary=architecture_summary,
        vulnerabilities=vulnerabilities,
        attack_scenarios=attack_scenarios,
        report=report,
        raw_results=json_data,
    )


# ============================================================
# Markdown Parser (Fallback)
# ============================================================


def parse_markdown_report(md_path: Path, bicep_code: str) -> AnalysisResult:
    """
    Markdown 보고서를 파싱하여 AnalysisResult를 생성합니다.
    
    JSON 파싱이 실패했을 때 fallback으로 사용됩니다.
    """
    logger.info("Falling back to Markdown parsing")
    
    if not md_path.exists():
        logger.error(f"Markdown report not found: {md_path}")
        return AnalysisResult(
            architecture_summary={"error": "Report not found"},
            vulnerabilities=[],
            attack_scenarios=[],
            report="Analysis failed - no report generated",
            raw_results={},
        )
    
    report_text = md_path.read_text()
    
    # 간단한 파싱: 제목과 심각도 키워드로 취약점 추출
    vulnerabilities = []
    
    # "Critical", "High" 등의 키워드 찾기
    severity_pattern = r'(Critical|High|Medium|Low)[\s:]+(.+?)(?=\n|$)'
    matches = re.findall(severity_pattern, report_text, re.IGNORECASE)
    
    for i, (severity, title) in enumerate(matches[:10]):  # 최대 10개
        vuln = VulnerabilityItem(
            id=f"VULN-MD-{i+1:03d}",
            severity=severity.capitalize(),
            category="Extracted from report",
            affected_resource="Unknown",
            title=title.strip()[:100],
            description=f"Extracted from markdown report",
            evidence="See full report",
            remediation="See full report",
            benchmark_ref="",
        )
        vulnerabilities.append(vuln)
    
    logger.info(f"Extracted {len(vulnerabilities)} vulnerabilities from markdown")
    
    return AnalysisResult(
        architecture_summary={"bicep_length": len(bicep_code)},
        vulnerabilities=vulnerabilities,
        attack_scenarios=[],  # Markdown에서 추출하기 어려움
        report=report_text,
        raw_results={"source": "markdown_fallback"},
    )


# ============================================================
# Main Wrapper Function
# ============================================================


async def analyze_bicep(bicep_code: str, agent_mode: AgentMode = "with-tools") -> AnalysisResult:
    """
    API 호환 함수: Bicep 코드 문자열을 받아 AnalysisResult를 반환합니다.
    
    Args:
        bicep_code: Bicep 코드 문자열
        agent_mode: Agent 실행 모드
            - "zero-tools": 완전 자율 Agent (느림, 창의적, 3-5분)
            - "with-tools": 도구 함수 사용 (빠름, 일관적, 10-30초)
        
    Returns:
        AnalysisResult: 구조화된 분석 결과
    """
    logger.info(f"🔄 Starting new_agent wrapper (mode: {agent_mode})")
    
    # Agent 선택
    convert_func = (
        zero_tools_convert_and_attack if agent_mode == "zero-tools"
        else with_tools_convert
    )
    
    # 임시 디렉토리 생성
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # 1. Bicep 코드를 임시 파일로 저장
        bicep_file = tmpdir_path / "input.bicep"
        bicep_file.write_text(bicep_code)
        logger.info(f"📝 Saved Bicep code to {bicep_file}")
        
        # 2. Docker Compose 출력 경로 설정
        compose_file = tmpdir_path / "docker-compose.yml"
        
        # 3. Agent 실행
        try:
            logger.info(f"🤖 Running {agent_mode} agent...")
            await convert_func(str(bicep_file), str(compose_file))
            logger.info("✅ Agent completed successfully")
        except Exception as e:
            logger.error(f"❌ Agent execution failed: {e}")
            return AnalysisResult(
                architecture_summary={"error": str(e)},
                vulnerabilities=[],
                attack_scenarios=[],
                report=f"## Analysis Failed\n\nError: {str(e)}",
                raw_results={"error": str(e)},
            )
        
        # 4. JSON 파일 읽기 시도
        # Agent는 실행 디렉토리(프로젝트 루트)에 파일을 생성하므로 절대 경로 사용
        project_root = Path(__file__).parent.parent  # agents/new_agent_wrapper.py -> project root
        json_file = project_root / "security_analysis.json"
        
        if json_file.exists():
            try:
                json_data = json.loads(json_file.read_text())
                logger.info(f"✅ Found and parsed security_analysis.json ({agent_mode})")
                result = parse_json_to_analysis_result(json_data, bicep_code)
                
                # JSON 파일 정리
                json_file.unlink()
                
                return result
            except Exception as e:
                logger.warning(f"⚠️ JSON parsing failed: {e}, falling back to markdown")
        else:
            logger.warning(f"⚠️ security_analysis.json not found at {json_file}, falling back to markdown")
        
        # 5. Fallback: Markdown 파싱
        md_file = project_root / "red_team_security_report.md"
        result = parse_markdown_report(md_file, bicep_code)
        
        # Markdown 파일 정리
        if md_file.exists():
            md_file.unlink()
        
        return result


# ============================================================
# Test Function
# ============================================================


async def test_wrapper():
    """Wrapper 테스트"""
    bicep_code = """
resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'teststorage'
  location: 'eastus'
  kind: 'StorageV2'
}

resource webapp 'Microsoft.Web/sites@2022-03-01' = {
  name: 'testwebapp'
  location: 'eastus'
  properties: {
    httpsOnly: true
  }
}
"""
    
    print("🧪 Testing new_agent_wrapper with with-tools mode")
    result = await analyze_bicep(bicep_code, agent_mode="with-tools")
    
    print(f"\n📊 Results:")
    print(f"  Vulnerabilities: {len(result.vulnerabilities)}")
    print(f"  Attack Scenarios: {len(result.attack_scenarios)}")
    print(f"  Report length: {len(result.report)}")
    
    for v in result.vulnerabilities[:3]:
        print(f"  - {v.severity}: {v.title}")


if __name__ == "__main__":
    asyncio.run(test_wrapper())
