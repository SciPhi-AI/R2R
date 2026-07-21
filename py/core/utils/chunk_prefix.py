"""Apply optional per-document chunk prefixes from metadata.

Pass ``chunk_prefix`` in document metadata on create; it is copied onto each
extraction and applied once in the embed path so vectors and stored text match.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

CHUNK_PREFIX_KEY = "chunk_prefix"
ORIGINAL_TEXT_KEY = "original_text"


def get_chunk_prefix(metadata: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Return a non-empty ``chunk_prefix`` from metadata, if present."""
    if not metadata:
        return None
    prefix = metadata.get(CHUNK_PREFIX_KEY)
    if not isinstance(prefix, str) or not prefix:
        return None
    return prefix


def strip_chunk_prefix(
    text: str, metadata: Optional[Mapping[str, Any]] = None
) -> str:
    """Return the unprefixed body for LLM/context use."""
    prefix = get_chunk_prefix(metadata)
    if not prefix:
        return text

    original = (metadata or {}).get(ORIGINAL_TEXT_KEY)
    if isinstance(original, str):
        return original
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


def apply_chunk_prefix(
    text: str,
    metadata: Optional[MutableMapping[str, Any] | Mapping[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """Prepend ``metadata.chunk_prefix`` for embedding and storage.

    - Records the unprefixed body in ``metadata.original_text``.
    - Idempotent if ``text`` already starts with the prefix.
    - No-op when ``chunk_prefix`` is missing or empty.

    Returns:
        ``(text_for_embed_and_store, metadata_copy)``
    """
    meta: dict[str, Any] = dict(metadata or {})
    prefix = get_chunk_prefix(meta)
    if not prefix:
        return text, meta

    if text.startswith(prefix):
        if ORIGINAL_TEXT_KEY not in meta or not isinstance(
            meta.get(ORIGINAL_TEXT_KEY), str
        ):
            meta[ORIGINAL_TEXT_KEY] = text[len(prefix) :]
        return text, meta

    meta[ORIGINAL_TEXT_KEY] = text
    return f"{prefix}{text}", meta
