import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from core.parsers.media.video_parser import VideoParser


class DummyApp:
    vlm = "test-vlm"


class DummyConfig:
    app = DummyApp()


@pytest_asyncio.fixture
def mock_db_provider():
    mock = MagicMock()
    mock.prompts_handler.get_cached_prompt = AsyncMock(
        return_value="prompt text"
    )
    return mock


@pytest_asyncio.fixture
def mock_llm_provider():
    mock = MagicMock()
    mock.aget_completion = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="video description"))]
        )
    )
    return mock


@pytest.mark.asyncio
async def test_ingest_str_success(mock_db_provider, mock_llm_provider):
    parser = VideoParser(
        config=DummyConfig(),
        database_provider=mock_db_provider,
        llm_provider=mock_llm_provider,
    )
    gen = parser.ingest(
        "http://test/video.mp4", file_type="mp4", bytes_limit=None
    )
    result = [x async for x in gen]
    assert result == ["video description"]


@pytest.mark.asyncio
async def test_ingest_bytes_success(mock_db_provider, mock_llm_provider):
    parser = VideoParser(
        config=DummyConfig(),
        database_provider=mock_db_provider,
        llm_provider=mock_llm_provider,
    )
    data = b"1234"
    gen = parser.ingest(data, file_type="mp4", bytes_limit=10)
    result = [x async for x in gen]
    assert result == ["video description"]


@pytest.mark.asyncio
async def test_ingest_invalid_file_type(mock_db_provider, mock_llm_provider):
    parser = VideoParser(
        config=DummyConfig(),
        database_provider=mock_db_provider,
        llm_provider=mock_llm_provider,
    )
    with pytest.raises(ValueError):
        gen = parser.ingest("http://test/video.xyz", file_type="xyz")
        [x async for x in gen]


@pytest.mark.asyncio
async def test_ingest_bytes_limit_exceeded(
    mock_db_provider, mock_llm_provider
):
    parser = VideoParser(
        config=DummyConfig(),
        database_provider=mock_db_provider,
        llm_provider=mock_llm_provider,
    )
    data = b"1" * 11
    with pytest.raises(ValueError):
        gen = parser.ingest(data, file_type="mp4", bytes_limit=10)
        [x async for x in gen]


@pytest.mark.asyncio
async def test_ingest_llm_no_response(mock_db_provider, mock_llm_provider):
    mock_llm_provider.aget_completion = AsyncMock(
        return_value=MagicMock(choices=[])
    )
    parser = VideoParser(
        config=DummyConfig(),
        database_provider=mock_db_provider,
        llm_provider=mock_llm_provider,
    )
    gen = parser.ingest("http://test/video.mp4", file_type="mp4")
    with pytest.raises(ValueError):
        [x async for x in gen]
