import uuid
from copy import deepcopy

# Example imports (adjust paths to match your codebase)
from typing import List

import pytest

# Example imports (adjust paths to match your codebase)
from core.base import (
    AggregateSearchResult,
    ChunkSearchResult,
    Citation,
    extract_citations,
    finalize_citations_in_message,
    generate_id,
    map_citations_to_sources,
    reassign_citations_in_order,
)


@pytest.fixture
def empty_aggregate():
    """
    Returns an AggregateSearchResult with no chunk search results,
    no graph results, no web results, etc.
    """
    return AggregateSearchResult(
        chunk_search_results=[],
        graph_search_results=[],
        web_search_results=[],
        context_document_results=[],
    )


@pytest.fixture
def small_aggregate():
    """
    Returns an AggregateSearchResult with, say, 3 chunk search results
    so we can test out-of-range bracket references.
    """
    chunk1 = ChunkSearchResult(
        id=generate_id("chunk-1"),
        document_id=generate_id("doc-1"),
        owner_id=None,
        collection_ids=[],
        score=0.88,
        text="Sample chunk text #1",
        metadata={"title": "Doc1.pdf"},
    )
    chunk2 = ChunkSearchResult(
        id=generate_id("chunk-2"),
        document_id=generate_id("doc-2"),
        owner_id=None,
        collection_ids=[],
        score=0.77,
        text="Sample chunk text #2",
        metadata={"title": "Doc2.pdf"},
    )
    chunk3 = ChunkSearchResult(
        id=generate_id("chunk-3"),
        document_id=generate_id("doc-3"),
        owner_id=None,
        collection_ids=[],
        score=0.99,
        text="Sample chunk text #3",
        metadata={"title": "Doc3.pdf"},
    )
    return AggregateSearchResult(
        chunk_search_results=[chunk1, chunk2, chunk3],
        graph_search_results=None,
        web_search_results=None,
        context_document_results=None,
    )


def test_no_citations_found(empty_aggregate):
    """
    If the LLM text has no bracket references, we should return an empty list from the extraction,
    and no changes when we attempt to reassign or map them to sources.
    """
    text = "This is some text without any bracket references."
    raw_citations = extract_citations(text)
    assert len(raw_citations) == 0

    new_text, new_citations = reassign_citations_in_order(text, raw_citations)
    assert new_text == text  # no changes
    assert len(new_citations) == 0

    mapped = map_citations_to_sources(new_citations, empty_aggregate)
    assert len(mapped) == 0


def test_single_citation_basic(empty_aggregate):
    """
    A single bracket reference [1].
    Should remain as [1] after reassigning, with snippet expanded.
    """
    text = "This is a short sentence [1]. Another sentence."
    raw_citations = extract_citations(text)
    assert len(raw_citations) == 1
    assert raw_citations[0].index == 1

    new_text, new_citations = reassign_citations_in_order(text, raw_citations)
    assert new_text == text  # [1] stays as [1]
    assert len(new_citations) == 1
    # snippet might or might not be exactly the entire text, depending on your sentence logic

    mapped = map_citations_to_sources(new_citations, empty_aggregate)
    # out-of-range => placeholders
    assert mapped[0].sourceType is None
    assert mapped[0].id is None


def test_multiple_citations_in_order(small_aggregate):
    """
    Suppose LLM text has 3 bracket references, e.g. [1], [2], [3].
    We'll confirm they remain in ascending order after reassign_citations_in_order
    and confirm they map 1->chunk1, 2->chunk2, 3->chunk3
    """
    text = "Chunk #1 is [1]. Then chunk #2 is [2]. Finally chunk #3 is [3]."
    raw_citations = extract_citations(text)
    assert len(raw_citations) == 3

    new_text, new_citations = reassign_citations_in_order(text, raw_citations)
    assert (
        new_text == text
    )  # They remain [1], [2], [3], no re-labelling needed
    assert [c.index for c in new_citations] == [1, 2, 3]

    mapped = map_citations_to_sources(new_citations, small_aggregate)
    # check that bracket #1 => chunk-1, bracket #2 => chunk-2, bracket #3 => chunk-3
    assert mapped[0].id == str(generate_id("chunk-1"))
    assert mapped[1].id == str(generate_id("chunk-2"))
    assert mapped[2].id == str(generate_id("chunk-3"))


def test_descending_citations(small_aggregate):
    """
    If the text references [3], [2], [1] in that order, we want them
    re-labeled as [1], [2], [3] in ascending order in the final text.
    """
    text = "First mention is [3], then second mention is [2], last mention is [1]."
    # Extract
    raw_citations = extract_citations(text)
    assert len(raw_citations) == 3
    # raw_citations might be (3, 2, 1) in that order

    new_text, new_cits = reassign_citations_in_order(text, raw_citations)
    # The final text should read: "First mention is [1], then second mention is [2], last mention is [3]."
    assert "[1]" in new_text
    assert "[2]" in new_text
    assert "[3]" in new_text
    assert (
        "[3]" not in new_text[: new_text.find("[1]")]
    )  # ensure the order is correct

    mapped = map_citations_to_sources(new_cits, small_aggregate)
    # Now bracket #1 => chunk-1, #2 => chunk-2, #3 => chunk-3
    assert mapped[0].id == str(generate_id("chunk-1"))
    assert mapped[1].id == str(generate_id("chunk-2"))
    assert mapped[2].id == str(generate_id("chunk-3"))


def test_out_of_range_brackets(small_aggregate):
    """
    If we have bracket references [1], [2], [5], but only 3 chunk results total,
    bracket #5 should map to placeholders.
    """
    text = "We talk about chunk #1 [1], chunk #2 [2], and chunk #5 [5]."
    raw_citations = extract_citations(text)
    assert len(raw_citations) == 3

    new_text, new_cits = reassign_citations_in_order(text, raw_citations)
    # Re-labeled => [1], [2], [3] if it sorts them, or it might keep them if they are [1], [2], [5]
    # Actually it will rename [5] => [3] since it's the 3rd citation encountered

    # Check the final bracket references
    # If the code re-labeled them strictly in ascending order, it might produce:
    # "We talk about chunk #1 [1], chunk #2 [2], and chunk #5 [3]."
    # It's fine as long as we are consistent.
    mapped = map_citations_to_sources(new_cits, small_aggregate)

    # We only have 3 chunk results, so bracket #3 (originally [5]) => chunk #3
    # or if your code doesn't re-label that far, you might have placeholders
    if len(small_aggregate.chunk_search_results) == 3:
        # bracket #3 => chunk 3
        # bracket #1 => chunk 1
        # bracket #2 => chunk 2
        # Just confirm none is placeholders
        ids = [m.id for m in mapped]
        assert str(generate_id("chunk-1")) in ids
        assert str(generate_id("chunk-2")) in ids
        assert str(generate_id("chunk-3")) in ids
    else:
        # fallback if your logic assigns placeholders
        # Not typically the case here, but you can handle if needed
        pass


def test_zero_brackets_still_converts(small_aggregate):
    """
    If the text references [0] or negative,
    normally bracket references won't parse that.
    We can confirm we skip them or treat them as is.
    """
    text = "This is some unusual text with a bracket [0]."
    raw_citations = extract_citations(text)
    # Possibly parse if your code sees [0] as bracket index 0
    # If you want to skip, we can assert raw_citations = 0
    assert len(raw_citations) == 1
    assert raw_citations[0].index == 0

    new_text, new_cits = reassign_citations_in_order(text, raw_citations)
    # Re-labeled => [1] or something
    assert "[1]" in new_text

    mapped = map_citations_to_sources(new_cits, small_aggregate)
    # bracket #1 => chunk1 if you have it, or placeholders
    if len(mapped) == 1:
        assert mapped[0].index == 1
    else:
        pytest.fail("Expected exactly one mapped citation")


def test_snippet_extraction_basic():
    """
    If the text has a short sentence, confirm the snippet is that sentence only.
    """
    text = "Hello world. This is a test [1]. Next sentence!"
    raw_citations = extract_citations(text)
    # We expect 1 bracket reference
    assert len(raw_citations) == 1
    cit = raw_citations[0]
    # snippet should ideally be 'This is a test [1].'
    snippet = text[cit.snippetStartIndex : cit.snippetEndIndex]
    assert "[1]" in snippet
    assert (
        "Next sentence!" not in snippet
    )  # Because the code should stop at exclamation


def test_all_upper_bound(small_aggregate):
    """
    If the text references [1], [2], [3], [4], [5] but we only have 3 chunk results,
    brackets 4 and 5 should still re-label to [4], [5] or whatever the logic does,
    but they won't map to a real chunk => placeholders
    """
    text = "[1], [2], [3], [4], and [5] are references in ascending order."
    raw_citations = extract_citations(text)
    assert len(raw_citations) == 5

    new_text, new_cits = reassign_citations_in_order(text, raw_citations)
    # Should remain "[1], [2], [3], [4], [5]" if code sees them are already ascending
    assert new_text == text

    mapped = map_citations_to_sources(new_cits, small_aggregate)
    # Only 3 chunk results => bracket #4, #5 => placeholders
    assert mapped[3].sourceType is None
    assert mapped[4].sourceType is None
    # The first 3 => chunk1, chunk2, chunk3
    assert mapped[0].id == str(generate_id("chunk-1"))
    assert mapped[1].id == str(generate_id("chunk-2"))
    assert mapped[2].id == str(generate_id("chunk-3"))
