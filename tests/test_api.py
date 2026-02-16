import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_analyze_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/analyze",
            files={"file": ("test.png", b"fake image content", "image/png")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["task_id"] != ""

    # steps 확인
    step_names = [s["step"] for s in data["steps"]]
    assert "파일 업로드" in step_names
    assert "RedTeam 분석" in step_names

    # security 결과 확인
    security = data["security"]
    assert len(security["vulnerabilities"]) > 0
    assert len(security["attack_scenarios"]) > 0
    assert "보안 평가 보고서" in security["report"]


@pytest.mark.asyncio
async def test_analyze_with_policy():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/analyze",
            files={"file": ("test.pdf", b"fake pdf", "application/pdf")},
            data={"skip_policy": "false"},
        )
    data = resp.json()
    assert data["status"] == "success"
    assert data["policy"] is not None
    assert data["policy"]["status"] in ("passed", "failed")


@pytest.mark.asyncio
async def test_analyze_skip_policy():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", b"fake jpg", "image/jpeg")},
            data={"skip_policy": "true"},
        )
    data = resp.json()
    assert data["status"] == "success"
    assert data["policy"] is None


@pytest.mark.asyncio
async def test_analyze_invalid_file_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/analyze",
            files={"file": ("test.txt", b"text content", "text/plain")},
        )
    assert resp.status_code == 400
    assert "지원하지 않는" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_no_file():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/analyze")
    assert resp.status_code == 422  # FastAPI validation error
