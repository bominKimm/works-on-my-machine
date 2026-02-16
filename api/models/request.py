from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """파일 분석 요청 시 추가 옵션 (multipart form과 함께 전송)."""
    skip_policy: bool = Field(default=False, description="Policy Agent 검증 건너뛰기")
