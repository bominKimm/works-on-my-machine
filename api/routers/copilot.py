import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
        from copilot import CopilotClient
        from copilot.types import CopilotClientOptions
        COPILOT_AVAILABLE = True
except ImportError:
        COPILOT_AVAILABLE = False
        CopilotClient = None
        CopilotClientOptions = dict

logger = logging.getLogger(__name__)

router = APIRouter()


class CopilotRequest(BaseModel):
        prompt: str = Field(default="What is 2 + 2?", description="Copilot에 보낼 프롬프트")
        model: str = Field(default="gpt-4.1", description="사용할 모델")
        timeout: float = Field(default=120.0, description="응답 대기 타임아웃(초)")


class CopilotResponse(BaseModel):
        status: str
        prompt: str
        model: str
        content: str | None = None
        error: str | None = None


@router.post("/copilot", response_model=CopilotResponse)
async def test_copilot(req: CopilotRequest):
        """GitHub Copilot SDK 실행 테스트."""
        if not COPILOT_AVAILABLE:
                    raise HTTPException(
                                    status_code=503,
                                    detail="GitHub Copilot SDK가 설치되어 있지 않습니다. requirements.txt에 copilot 패키지를 추가하세요.",
                    )
                client_opts: CopilotClientOptions = {}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
                client_opts["github_token"] = github_token
                client_opts["use_logged_in_user"] = False
            try:
                        client = CopilotClient(client_opts)
                        response = await client.ask(
                            prompt=req.prompt,
                            model=req.model,
                            timeout=req.timeout,
                        )
                        return CopilotResponse(
                            status="success",
                            prompt=req.prompt,
                            model=req.model,
                            content=str(response),
                        )
except Exception as e:
        logger.error("Copilot 호출 실패: %s", e)
        return CopilotResponse(
                        status="error",
                        prompt=req.prompt,
                        model=req.model,
                        error=str(e),
        )
