"""보안 분석 결과 기반 챗봇 API."""

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from copilot import CopilotClient
from copilot.types import CopilotClientOptions

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(description="사용자 질문")
    context: dict = Field(default_factory=dict, description="분석 결과 컨텍스트")
    history: list[dict] = Field(default_factory=list, description="이전 대화 내역")
    model: str = Field(default="gpt-4.1", description="사용할 모델")


class ChatResponse(BaseModel):
    status: str
    answer: str | None = None
    error: str | None = None


def _build_prompt(context: dict, history: list[dict], question: str) -> str:
    security = context.get("security") or {}
    policy = context.get("policy")
    vulns = security.get("vulnerabilities") or []
    attacks = security.get("attack_scenarios") or []
    report = security.get("report") or ""

    lines = [
        "당신은 Azure 클라우드 보안 분석 전문가입니다.",
        "아래는 자동 보안 분석 결과입니다. 이 데이터를 근거로 사용자 질문에 한국어로 전문적이고 구체적으로 답변하세요.",
        "",
        "## 취약점 목록",
    ]

    if vulns:
        for v in vulns:
            lines.append(
                f"- [{v.get('severity')}] {v.get('id')}: {v.get('title')} "
                f"(영향 리소스: {v.get('affected_resource')}) — {v.get('description')} "
                f"| 수정 방법: {v.get('remediation')}"
            )
    else:
        lines.append("취약점 없음")

    lines += ["", "## 공격 시나리오"]
    if attacks:
        for a in attacks:
            chain = " → ".join(a.get("attack_chain") or [])
            lines.append(
                f"- [{a.get('severity')}] {a.get('id')}: {a.get('name')} "
                f"(MITRE: {a.get('mitre_technique')}) | 체인: {chain} | "
                f"예상 피해: {a.get('expected_impact')}"
            )
    else:
        lines.append("공격 시나리오 없음")

    lines += ["", "## Policy 검증 결과"]
    if policy:
        lines.append(f"상태: {policy.get('status', 'N/A')}")
        for v in policy.get("violations") or []:
            lines.append(f"- 위반 [{v.get('rule')}] {v.get('severity', '').upper()}: {v.get('message')} — {v.get('recommendation')}")
        for r in policy.get("recommendations") or []:
            lines.append(f"- 권장 [{r.get('rule')}] {r.get('severity', '').upper()}: {r.get('message')} — {r.get('recommendation')}")
    else:
        lines.append("Policy 검증 건너뜀")

    if report:
        lines += ["", "## 보안 보고서 (요약)"]
        lines.append(report[:3000] + ("..." if len(report) > 3000 else ""))

    if history:
        lines += ["", "## 이전 대화"]
        for msg in history[-6:]:
            role = "사용자" if msg.get("role") == "user" else "어시스턴트"
            lines.append(f"{role}: {msg.get('content', '')}")

    lines += ["", "## 현재 질문", question]
    return "\n".join(lines)


@router.post("/chat", response_model=ChatResponse)
async def security_chat(req: ChatRequest):
    """분석 결과를 컨텍스트로 보안 질문에 답변합니다."""
    client_opts: CopilotClientOptions = {}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        client_opts["github_token"] = github_token
        client_opts["use_logged_in_user"] = False

    client = CopilotClient(client_opts if client_opts else None)
    try:
        await client.start()
        session = await client.create_session({"model": req.model})
        prompt = _build_prompt(req.context, req.history, req.question)
        response = await session.send_and_wait({"prompt": prompt}, timeout=120.0)

        content = None
        if response and response.data:
            content = response.data.content

        return ChatResponse(status="success", answer=content or "응답을 받지 못했습니다.")
    except Exception as e:
        logger.exception("Chat API 호출 실패")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.stop()
