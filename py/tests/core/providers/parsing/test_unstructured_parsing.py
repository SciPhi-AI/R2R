from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core import generate_id_from_label
from core.base import Document, DocumentExtraction, DocumentType
from core.providers.parsing.unstructured_parsing import FallbackElement


@pytest.mark.asyncio
async def test_parse_fallback(unstructured_parsing_provider):
    document = Document(
        id=generate_id_from_label("test_parse_fallback"),
        collection_ids=[],
        user_id=generate_id_from_label("test_user"),
        type=DocumentType.PNG,
        metadata={},
    )
    chunk_size = 128

    async def mock_ingest(file_content, chunk_size):
        for text in ["text1", "text2"]:
            yield text

    mock_parser = AsyncMock()
    mock_parser.ingest = mock_ingest
    unstructured_parsing_provider.parsers[DocumentType.PNG] = mock_parser

    elements = [
        element
        async for element in unstructured_parsing_provider.parse_fallback(
            b"test_data", document, chunk_size
        )
    ]

    assert len(elements) == 2
    assert isinstance(elements[0], FallbackElement)
    assert elements[0].text == "text1"
    assert elements[0].metadata == {"chunk_id": 0}
    assert isinstance(elements[1], FallbackElement)
    assert elements[1].text == "text2"
    assert elements[1].metadata == {"chunk_id": 1}


@pytest.mark.asyncio
async def test_parse_with_local_unstructured(unstructured_parsing_provider):
    document = Document(
        id=generate_id_from_label("test_parse_with_local_unstructured"),
        collection_ids=[],
        user_id=generate_id_from_label("test_user"),
        type=DocumentType.DOCX,
        metadata={"title": "test_title"},
    )

    async def mock_post(url, json, **kwargs):
        return MagicMock(
            json=MagicMock(return_value={"elements": [{"text": "test_text"}]})
        )

    with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        extractions = [
            extraction
            async for extraction in unstructured_parsing_provider.parse(
                BytesIO(b"test_data"), document
            )
        ]

    assert len(extractions) == 1
    assert isinstance(extractions[0], DocumentExtraction)
    assert extractions[0].data == "test_text"
    assert extractions[0].metadata["partitioned_by_unstructured"] is True
