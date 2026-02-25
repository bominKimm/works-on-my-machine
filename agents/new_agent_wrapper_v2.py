"""
Agent Wrapper V2: Agent의 stdout에서 JSON을 추출하여 API response로 반환

두 가지 Agent 모드 지원:
- "zero-tools": 완전 자율 Agent (느리지만 창의적)
- "with-tools": 도구 함수 사용 Agent (빠르고 일관적)
"""

import asyncio
import json
import logging
import os
import re
import sys
import io
import tempfile
from pathlib import Path
from typing import Optional, Literal
from contextlib import redirect_stdout

from agents.agent import AnalysisResult, VulnerabilityItem, AttackScenario
from agents.new_agent import convert_and_attack as zero_tools_convert_and_attack
from agents.new_agent_with_tools import convert_bicep_to_compose as with_tools_convert

# 로깅 설정
logger = logging.getLogger(__name__)

# Agent 모드 타입
AgentMode = Literal["zero-tools", "with-tools"]


# ============================================================
# JSON 파싱 함수 (기존 유지)
# ============================================================


def parse_json_to_analysis_result(json_data: dict, bicep_code: str) -> AnalysisResult:
    """
    Agent가 출력한 JSON 데이터를 AnalysisResult로 변환
    
    Args:
        json_data: Agent가 출력한 JSON 데이터
        bicep_code: 원본 Bicep 코드
        
    Returns:
        AnalysisResult: API 호환 형식
    """
    vulnerabilities = []
    for v in json_data.get("vulnerabilities", []):
        vulnerabilities.append(
            VulnerabilityItem(
                id=v.get("id", "UNKNOWN"),
                severity=v.get("severity", "Medium"),
                category=v.get("category", "Unknown"),
                affected_resource=v.get("affected_resource", "Unknown"),
                title=v.get("title", "Unknown Vulnerability"),
                description=v.get("description", "No description"),
                evidence=v.get("evidence", "No evidence"),
                remediation=v.get("remediation", "No remediation"),
                benchmark_ref=v.get("benchmark_ref", "N/A"),
            )
        )
    
    attack_scenarios = []
    for a in json_data.get("attack_scenarios", []):
        # prerequisites가 리스트인 경우 문자열로 변환
        prerequisites = a.get("prerequisites", "None")
        if isinstance(prerequisites, list):
            prerequisites = "; ".join(prerequisites)
        
        attack_scenarios.append(
            AttackScenario(
                id=a.get("id", "UNKNOWN"),
                name=a.get("name", "Unknown Attack"),
                mitre_technique=a.get("mitre_technique", "N/A"),
                target_vulnerabilities=a.get("target_vulnerabilities", []),
                severity=a.get("severity", "Medium"),
                prerequisites=prerequisites,
                attack_chain=a.get("attack_chain", []),
                expected_impact=a.get("expected_impact", "Unknown"),
                detection_difficulty=a.get("detection_difficulty", "Unknown"),
                likelihood=a.get("likelihood", "Unknown"),
            )
        )
    
    # Architecture summary 생성
    architecture_summary = {
        "bicep_resources": len(bicep_code.split("resource ")),
        "total_vulnerabilities": len(vulnerabilities),
        "total_attack_scenarios": len(attack_scenarios),
        "data_source": "JSON (parsed from agent stdout)",
    }

    # Agent가 생성한 report 사용
    report = json_data.get("report", "")

    return AnalysisResult(
        architecture_summary=architecture_summary,
        vulnerabilities=vulnerabilities,
        attack_scenarios=attack_scenarios,
        report=report,
        raw_results=json_data,
    )


def parse_markdown_report(md_file: Path, bicep_code: str) -> AnalysisResult:
    """
    Markdown 리포트 파싱 (Fallback)
    
    Args:
        md_file: Markdown 파일 경로
        bicep_code: 원본 Bicep 코드
        
    Returns:
        AnalysisResult: API 호환 형식
    """
    if not md_file.exists():
        logger.warning(f"⚠️ Markdown file not found: {md_file}")
        return AnalysisResult(
            architecture_summary={"error": "No report generated"},
            vulnerabilities=[],
            attack_scenarios=[],
            report="# No Report Generated\n\nAgent did not produce any output.",
            raw_results={},
        )
    
    report = md_file.read_text()
    
    # 간단한 파싱: 취약점 개수 추출
    vuln_count = len(re.findall(r"##\s+취약점|##\s+Vulnerability", report, re.IGNORECASE))
    
    # 더미 취약점 생성 (Markdown에서 파싱)
    vulnerabilities = []
    for i in range(min(vuln_count, 5)):  # 최대 5개
        vulnerabilities.append(
            VulnerabilityItem(
                id=f"VULN-{i+1:03d}",
                severity="Medium",
                category="Configuration",
                affected_resource="Unknown",
                title=f"Issue {i+1} (from Markdown)",
                description="Parsed from Markdown report",
                evidence="See detailed report",
                remediation="Review Markdown for details",
                benchmark_ref="N/A",
            )
        )
    
    return AnalysisResult(
        architecture_summary={
            "bicep_resources": len(bicep_code.split("resource ")),
            "total_vulnerabilities": len(vulnerabilities),
            "data_source": "Markdown fallback",
        },
        vulnerabilities=vulnerabilities,
        attack_scenarios=[],
        report=report,
        raw_results={"markdown": report[:500]},
    )


# ============================================================
# Main Wrapper Function
# ============================================================


async def analyze_bicep(
    bicep_code: str, agent_mode: AgentMode = "with-tools"
) -> AnalysisResult:
    """
    Bicep 코드를 분석하고 보안 취약점을 찾아 반환 (V2: Agent 응답을 JSON으로 파싱)
    
    Args:
        bicep_code: Bicep 코드 문자열
        agent_mode: Agent 실행 모드
            - "zero-tools": 완전 자율 Agent (느림, 창의적, 3-5분)
            - "with-tools": 도구 함수 사용 (빠름, 일관적, 10-30초)
        
    Returns:
        AnalysisResult: 구조화된 분석 결과
    """
    logger.info(f"🔄 Starting new_agent wrapper V2 (mode: {agent_mode})")
    
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
        agent_response = None
        agent_response_text = ""
        try:
            logger.info(f"🤖 Running {agent_mode} agent...")
            agent_response = await convert_func(str(bicep_file), str(compose_file))
            
            # AgentResponse 객체를 문자열로 변환
            if hasattr(agent_response, 'message'):
                agent_response_text = agent_response.message
            elif hasattr(agent_response, 'content'):
                agent_response_text = agent_response.content
            else:
                agent_response_text = str(agent_response)
            
            logger.info("✅ Agent completed successfully")
            logger.debug(f"Agent response length: {len(agent_response_text)} chars")
            
        except Exception as e:
            logger.error(f"❌ Agent execution failed: {e}", exc_info=True)
            return AnalysisResult(
                architecture_summary={"error": str(e)},
                vulnerabilities=[],
                attack_scenarios=[],
                report=f"## Analysis Failed\n\nError: {str(e)}",
                raw_results={"error": str(e)},
            )
        
        # 4. Agent 응답을 JSON으로 파싱 시도
        # Agent가 마지막 응답으로 JSON을 반환했을 것으로 기대
        try:
            # 응답에서 JSON 객체 추출 (```json ... ``` 마크다운 코드 블록 포함 가능)
            json_match = re.search(r'```json\s*\n(.*?)\n```', agent_response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 마크다운 없이 바로 JSON인 경우
                # 마지막 { ... } 블록 찾기
                json_match = re.search(r'(\{[\s\S]*"vulnerabilities"[\s\S]*\})\s*$', agent_response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # 전체 응답이 JSON인지 시도
                    json_str = agent_response_text.strip()
            
            json_data = json.loads(json_str)
            logger.info(f"✅ Parsed JSON from agent response ({agent_mode})")
            logger.info(f"   - Vulnerabilities: {len(json_data.get('vulnerabilities', []))}")
            logger.info(f"   - Attack scenarios: {len(json_data.get('attack_scenarios', []))}")
            return parse_json_to_analysis_result(json_data, bicep_code)
            
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"⚠️ JSON parsing failed: {e}")
            logger.debug(f"Agent response preview: {agent_response_text[:500]}...")
        
        # 5. Fallback: Markdown 파싱
        logger.info("⚠️ Falling back to Markdown parsing...")
        project_root = Path(__file__).parent.parent
        md_file = project_root / "red_team_security_report.md"
        result = parse_markdown_report(md_file, bicep_code)
        
        # Markdown 파일 정리
        if md_file.exists():
            md_file.unlink()
            logger.info(f"🗑️ Cleaned up {md_file}")
        
        return result


# ============================================================
# Test Function
# ============================================================


async def test_wrapper():
    """Wrapper V2 테스트"""
    bicep_code = """
resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'teststorage'
  location: 'eastus'
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}
"""
    
    print("🧪 Testing new_agent_wrapper V2...")
    result = await analyze_bicep(bicep_code, agent_mode="with-tools")
    
    print(f"\n✅ Analysis complete!")
    print(f"   - Vulnerabilities: {len(result.vulnerabilities)}")
    print(f"   - Attack scenarios: {len(result.attack_scenarios)}")
    print(f"   - Data source: {result.architecture_summary.get('data_source')}")


if __name__ == "__main__":
    asyncio.run(test_wrapper())
