import pytest

from core.base import R2RException
from core.parsers.structured.json_parser import JSONParser


@pytest.mark.asyncio
@pytest.mark.parametrize("chunk_size", [-1, -4])
async def test_negative_chunk_size_is_rejected(chunk_size):
    parser = JSONParser(None, None, None)
    with pytest.raises(ValueError, match="chunk_size"):
        [
            chunk
            async for chunk in parser.ingest('{"text": "hello"}', chunk_size=chunk_size)
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("data", ['{"text": "hello"}', b'{"text": "hello"}'])
@pytest.mark.parametrize(
    "chunk_size, expected",
    [(None, ["text: hello"]), (0, ["text: hello"]), (4, ["text", ": he", "llo"])],
)
async def test_valid_chunk_sizes_preserve_content(data, chunk_size, expected):
    parser = JSONParser(None, None, None)
    assert [
        chunk async for chunk in parser.ingest(data, chunk_size=chunk_size)
    ] == expected


@pytest.mark.asyncio
async def test_invalid_json_keeps_parse_error():
    parser = JSONParser(None, None, None)
    with pytest.raises(R2RException, match="Failed to parse JSON data") as exc:
        [chunk async for chunk in parser.ingest("{", chunk_size=-1)]
    assert exc.value.status_code == 400
