"""Unit tests for metadata-driven chunk prefixing (Plan B)."""

from core.utils.chunk_prefix import (
    CHUNK_PREFIX_KEY,
    ORIGINAL_TEXT_KEY,
    apply_chunk_prefix,
    get_chunk_prefix,
    strip_chunk_prefix,
)


def test_get_chunk_prefix_empty_cases():
    assert get_chunk_prefix(None) is None
    assert get_chunk_prefix({}) is None
    assert get_chunk_prefix({CHUNK_PREFIX_KEY: ""}) is None
    assert get_chunk_prefix({CHUNK_PREFIX_KEY: 123}) is None  # type: ignore[dict-item]


def test_apply_chunk_prefix_none():
    text, meta = apply_chunk_prefix("hello", {})
    assert text == "hello"
    assert ORIGINAL_TEXT_KEY not in meta


def test_apply_chunk_prefix_prepends_and_records_original():
    prefix = "Tenant:Acme | "
    text, meta = apply_chunk_prefix("body", {CHUNK_PREFIX_KEY: prefix})
    assert text == f"{prefix}body"
    assert meta[ORIGINAL_TEXT_KEY] == "body"
    assert meta[CHUNK_PREFIX_KEY] == prefix


def test_apply_chunk_prefix_idempotent():
    prefix = "P:"
    once, meta1 = apply_chunk_prefix("body", {CHUNK_PREFIX_KEY: prefix})
    twice, meta2 = apply_chunk_prefix(once, meta1)
    assert once == twice == "P:body"
    assert meta2[ORIGINAL_TEXT_KEY] == "body"


def test_strip_prefers_original_text():
    meta = {
        CHUNK_PREFIX_KEY: "P:",
        ORIGINAL_TEXT_KEY: "stored-body",
    }
    assert strip_chunk_prefix("P:other", meta) == "stored-body"


def test_strip_without_original_uses_startswith():
    meta = {CHUNK_PREFIX_KEY: "P:"}
    assert strip_chunk_prefix("P:body", meta) == "body"
    assert strip_chunk_prefix("no-prefix", meta) == "no-prefix"
