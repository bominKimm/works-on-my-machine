import asyncio
from pathlib import Path


SAMPLE_BICEP_PATH = (
    Path(__file__).parent.parent
    / "samples"
    / "bicep_sample_07_web_storage_compliant.bicep"
)


async def mock_bicep_transform(file_content: bytes, filename: str) -> str:
    """
    Mock BiCep 변환 서비스.

    실제 구현 예정:
    - LLM 호출하여 아키텍처 다이어그램 → BiCep 코드 변환
    - Azure Blob 저장

    현재는 샘플 BiCep 코드를 반환합니다.
    """
    # LLM 호출 시뮬레이션을 위한 지연
    await asyncio.sleep(1.0)

    # 샘플 BiCep 코드 반환
    if SAMPLE_BICEP_PATH.exists():
        return SAMPLE_BICEP_PATH.read_text(encoding="utf-8")

    return _get_default_bicep()


def _get_default_bicep() -> str:
    """샘플 파일이 없을 경우 기본 BiCep 코드 반환."""
    return """\
param location string = resourceGroup().location

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'defaultstorage'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}
"""
