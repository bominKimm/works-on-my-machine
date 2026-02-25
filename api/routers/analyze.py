import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from agents.mock_agents import mock_policy_agent
from agents.agent import LocalAttackAgent  # LocalAttackAgent를 RedTeam Agent로 사용
from api.models.response import (
    AnalyzeResponse,
    AttackScenarioItem,
    PolicyResult,
    SecurityResult,
    StepStatus,
    VulnerabilityItem,
)
from mock_services.bicep_transformer import mock_bicep_transform
from mock_services.file_processor import mock_file_preprocessing

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _validate_file(filename: str, size: int) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식: {ext}. 지원: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기 초과: {size} bytes (최대 {MAX_FILE_SIZE} bytes)",
        )


async def _run_policy(bicep_code: str, skip: bool) -> tuple[PolicyResult | None, StepStatus]:
    if skip:
        return None, StepStatus(step="Policy 검증", status="completed", message="건너뜀")
    raw = await mock_policy_agent(bicep_code)
    return PolicyResult(**raw), StepStatus(step="Policy 검증", status="completed", message=raw["summary"])


async def _run_redteam(bicep_code: str):
    agent = LocalAttackAgent()  # LocalAttackAgent를 RedTeam Agent로 사용
    result = await agent.analyze(bicep_code)
    return result, StepStatus(step="RedTeam 분석", status="completed", message=f"취약점 {len(result.vulnerabilities)}개")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_architecture(
    file: UploadFile = File(...),
    skip_policy: bool = Form(default=False),
):
    """
    아키텍처 파일을 분석합니다.

    파이프라인:
    1. 파일 검증
    2. 파일 전처리 (Mock) → BiCep 변환 (Mock)
    3. Policy 검증 & RedTeam 분석 (병렬)
    """
    task_id = uuid.uuid4().hex[:12]
    steps: list[StepStatus] = []

    try:
        # --- Step 1: 파일 검증 ---
        content = await file.read()
        _validate_file(file.filename, len(content))
        steps.append(StepStatus(step="파일 업로드", status="completed", message=f"{file.filename} ({len(content)} bytes)"))

        # --- Step 2: 전처리 + BiCep 변환 (순차) ---
        await mock_file_preprocessing(content, file.filename)
        steps.append(StepStatus(step="파일 전처리", status="completed"))

        bicep_code = await mock_bicep_transform(content, file.filename)
        steps.append(StepStatus(step="BiCep 변환", status="completed", message=f"{len(bicep_code)} chars"))

        # --- Step 3+4: Policy 검증 & RedTeam 분석 (병렬) ---
        (policy_result, policy_step), (result, redteam_step) = await asyncio.gather(
            _run_policy(bicep_code, skip_policy),
            _run_redteam(bicep_code),
        )
        steps.append(policy_step)
        steps.append(redteam_step)

        security = SecurityResult(
            vulnerabilities=[
                VulnerabilityItem(
                    id=v.id,
                    severity=v.severity,
                    category=v.category,
                    affected_resource=v.affected_resource,
                    title=v.title,
                    description=v.description,
                    evidence=v.evidence,
                    remediation=v.remediation,
                    benchmark_ref=v.benchmark_ref,
                )
                for v in result.vulnerabilities
            ],
            attack_scenarios=[
                AttackScenarioItem(
                    id=a.id,
                    name=a.name,
                    mitre_technique=a.mitre_technique,
                    target_vulnerabilities=a.target_vulnerabilities,
                    severity=a.severity,
                    prerequisites=a.prerequisites,
                    attack_chain=a.attack_chain,
                    expected_impact=a.expected_impact,
                    detection_difficulty=a.detection_difficulty,
                    likelihood=a.likelihood,
                )
                for a in result.attack_scenarios
            ],
            vulnerability_summary=result.vulnerability_count,
            report=result.report,
        )

        # --- Step 5: 결과 종합 ---
        vuln_count = len(result.vulnerabilities)
        attack_count = len(result.attack_scenarios)
        steps.append(StepStatus(
            step="결과 종합",
            status="completed",
            message=f"취약점 {vuln_count}개 · 공격 {attack_count}개",
        ))

        return AnalyzeResponse(
            status="success",
            task_id=task_id,
            steps=steps,
            policy=policy_result,
            security=security,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("분석 중 오류 발생")
        steps.append(StepStatus(step="오류", status="error", message=str(e)))
        return AnalyzeResponse(
            status="error",
            task_id=task_id,
            steps=steps,
            error=str(e),
        )
