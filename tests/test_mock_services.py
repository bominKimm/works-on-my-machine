import pytest
import pytest_asyncio

from mock_services.file_processor import mock_file_preprocessing
from mock_services.bicep_transformer import mock_bicep_transform
from mock_services.blob_storage import mock_blob_storage, mock_blob_download, mock_blob_list


@pytest.mark.asyncio
async def test_file_preprocessing_returns_bicep():
    result = await mock_file_preprocessing(b"dummy", "arch.pdf")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "resource" in result  # BiCep 코드에는 resource 키워드가 있어야 함


@pytest.mark.asyncio
async def test_file_preprocessing_accepts_valid_extensions():
    for ext in (".pdf", ".png", ".jpg", ".jpeg"):
        result = await mock_file_preprocessing(b"x", f"file{ext}")
        assert len(result) > 0


@pytest.mark.asyncio
async def test_file_preprocessing_rejects_invalid_extension():
    with pytest.raises(ValueError, match="지원하지 않는"):
        await mock_file_preprocessing(b"x", "file.txt")


@pytest.mark.asyncio
async def test_bicep_transform_returns_bicep():
    result = await mock_bicep_transform(b"dummy", "arch.png")
    assert isinstance(result, str)
    assert "resource" in result


@pytest.mark.asyncio
async def test_blob_storage_upload_and_download():
    info = await mock_blob_storage("hello bicep", container="test")
    assert info["container"] == "test"
    assert info["size"] > 0

    data = await mock_blob_download("test", info["blob_name"])
    assert data == "hello bicep"


@pytest.mark.asyncio
async def test_blob_storage_list():
    await mock_blob_storage("data1", container="listtest", blob_name="a.bicep")
    await mock_blob_storage("data2", container="listtest", blob_name="b.bicep")
    items = mock_blob_list("listtest")
    names = [i["blob_name"] for i in items]
    assert "a.bicep" in names
    assert "b.bicep" in names


@pytest.mark.asyncio
async def test_blob_download_missing():
    result = await mock_blob_download("nocontainer", "nofile")
    assert result is None
