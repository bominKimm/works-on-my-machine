from pathlib import Path

import pytest

from agents.mock_agents import mock_policy_agent
from agents.redteam_agent import RedTeamAgent

SAMPLE_BICEP = (Path(__file__).parent.parent / "samples" / "sample_bicep.bicep").read_text()


# ---------------------------------------------------------------------------
# Policy Agent (Mock)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_agent_returns_structure():
    result = await mock_policy_agent(SAMPLE_BICEP)
    assert "status" in result
    assert "violations" in result
    assert "recommendations" in result
    assert isinstance(result["violations"], list)


@pytest.mark.asyncio
async def test_policy_agent_detects_wildcard_source():
    result = await mock_policy_agent(SAMPLE_BICEP)
    # sample_bicep.bicep에는 sourceAddressPrefix: '*' 가 있으므로 위반이 있어야 함
    assert result["status"] == "failed"
    assert len(result["violations"]) > 0


@pytest.mark.asyncio
async def test_policy_agent_clean_code():
    clean_bicep = """
    resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
      name: 'vnet'
      location: 'eastus'
    }
    """
    result = await mock_policy_agent(clean_bicep)
    assert result["status"] == "passed"
    assert len(result["violations"]) == 0


# ---------------------------------------------------------------------------
# RedTeam Agent (Mock)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redteam_analyze_returns_result():
    agent = RedTeamAgent()
    result = await agent.analyze(SAMPLE_BICEP)

    assert result.vulnerabilities is not None
    assert result.attack_scenarios is not None
    assert result.report is not None
    assert result.architecture_summary is not None


@pytest.mark.asyncio
async def test_redteam_finds_vulnerabilities():
    agent = RedTeamAgent()
    result = await agent.analyze(SAMPLE_BICEP)

    assert len(result.vulnerabilities) > 0
    severities = {v.severity for v in result.vulnerabilities}
    assert "Critical" in severities


@pytest.mark.asyncio
async def test_redteam_generates_attack_scenarios():
    agent = RedTeamAgent()
    result = await agent.analyze(SAMPLE_BICEP)

    assert len(result.attack_scenarios) > 0
    for atk in result.attack_scenarios:
        assert len(atk.attack_chain) > 0
        assert atk.mitre_technique != ""


@pytest.mark.asyncio
async def test_redteam_generates_report():
    agent = RedTeamAgent()
    result = await agent.analyze(SAMPLE_BICEP)

    assert "보안 평가 보고서" in result.report
    assert "취약점" in result.report
    assert "개선 로드맵" in result.report


@pytest.mark.asyncio
async def test_redteam_vulnerability_count():
    agent = RedTeamAgent()
    result = await agent.analyze(SAMPLE_BICEP)

    counts = result.vulnerability_count
    total = sum(counts.values())
    assert total == len(result.vulnerabilities)


@pytest.mark.asyncio
async def test_redteam_clean_code_no_vulns():
    agent = RedTeamAgent()
    result = await agent.analyze("resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {}")

    assert len(result.vulnerabilities) == 0
    assert len(result.attack_scenarios) == 0
