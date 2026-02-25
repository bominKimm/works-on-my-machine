import asyncio
import os
from pathlib import Path


SAMPLE_BICEP_PATH = Path(__file__).parent.parent / "samples" / "sample_bicep.bicep"


async def mock_file_preprocessing(file_content: bytes, filename: str) -> str:
    """
    Mock 파일 전처리 서비스.

    실제 구현 예정:
    - 파일 파싱 (5p씩 증분 방식)
    - Azure Blob 저장 (버전 관리)

    현재는 파일 형식을 확인한 후 샘플 BiCep 코드를 반환합니다.
    """
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".bicep"}  # Bicep 추가
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_extensions:
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {ext}. "
            f"지원 형식: {', '.join(allowed_extensions)}"
        )
    
    # Bicep 파일인 경우 그대로 반환
    if ext == ".bicep":
        await asyncio.sleep(0.1)  # 간단한 검증 시뮬레이션
        return file_content.decode('utf-8')

    # 실제 파싱 시뮬레이션을 위한 지연
    await asyncio.sleep(0.5)

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
