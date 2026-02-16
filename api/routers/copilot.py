import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from copilot import CopilotClient
from copilot.types import CopilotClientOptions

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
    client_opts: CopilotClientOptions = {}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        client_opts["github_token"] = github_token
        client_opts["use_logged_in_user"] = False  # CLI에 저장된 자격 증명 사용 안 함

    client = CopilotClient(client_opts if client_opts else None)
    try:
        await client.start()
        session = await client.create_session({"model": req.model})
        response = await session.send_and_wait(
            {"prompt": req.prompt},
            timeout=req.timeout,
        )

        content = None
        if response and response.data:
            content = response.data.content

        return CopilotResponse(
            status="success",
            prompt=req.prompt,
            model=req.model,
            content=content,
        )
    except Exception as e:
        logger.exception("Copilot SDK 호출 실패")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.stop()
