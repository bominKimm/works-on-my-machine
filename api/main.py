import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.analyze import router as analyze_router
from api.routers.copilot import router as copilot_router
from api.routers.health import router as health_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Azure Security Analyzer",
    description="Azure 아키텍처 보안 검증 에이전트 서비스",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(analyze_router, prefix="/api/v1", tags=["analyze"])
app.include_router(copilot_router, prefix="/api/v1", tags=["copilot"])
