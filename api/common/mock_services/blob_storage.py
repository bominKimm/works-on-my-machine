import asyncio
import uuid
from datetime import datetime, timezone


# 인메모리 스토리지 (Mock)
_storage: dict[str, dict] = {}


async def mock_blob_storage(data: str, container: str = "default", blob_name: str | None = None) -> dict:
    """
    Mock Azure Blob Storage 서비스.

    실제 구현 예정:
    - Azure Blob Storage SDK 사용
    - 버전 관리
    - SAS 토큰 기반 접근 제어

    현재는 인메모리 딕셔너리에 저장합니다.
    """
    if blob_name is None:
        blob_name = f"{uuid.uuid4().hex}.bicep"

    blob_key = f"{container}/{blob_name}"

    # 업로드 시뮬레이션
    await asyncio.sleep(0.2)

    _storage[blob_key] = {
        "data": data,
        "container": container,
        "blob_name": blob_name,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "size": len(data.encode("utf-8")),
    }

    return {
        "blob_url": f"https://mock.blob.core.windows.net/{blob_key}",
        "blob_name": blob_name,
        "container": container,
        "size": len(data.encode("utf-8")),
    }


async def mock_blob_download(container: str, blob_name: str) -> str | None:
    """Mock Blob 다운로드."""
    blob_key = f"{container}/{blob_name}"
    entry = _storage.get(blob_key)
    if entry is None:
        return None
    return entry["data"]


def mock_blob_list(container: str = "default") -> list[dict]:
    """Mock Blob 목록 조회."""
    results = []
    for key, value in _storage.items():
        if key.startswith(f"{container}/"):
            results.append({
                "blob_name": value["blob_name"],
                "size": value["size"],
                "uploaded_at": value["uploaded_at"],
            })
    return results
