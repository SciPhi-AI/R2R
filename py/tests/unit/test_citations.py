import re
import uuid
from copy import deepcopy

# Example imports (adjust paths to match your codebase)
from typing import List

import pytest

from core.agent import SearchResultsCollector

# Example imports (adjust paths to match your codebase)
from core.base import (
    AggregateSearchResult,
    ChunkSearchResult,
    Citation,
    GraphCommunityResult,
    GraphEntityResult,
    GraphRelationshipResult,
    GraphSearchResult,
    WebSearchResult,
    extract_citations,
    finalize_citations_in_message,
    generate_id,
    map_citations_to_collector,
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


def test_repeated_bracket_ref_basic(empty_aggregate):
    """
    If the text uses the same bracket [2] multiple times, we want them all to remain
    the same bracket index after relabeling.
    For instance, if rawIndex=2 is repeated 3 times, the final text might become
    [1],[1],[1] (if 2 is the first unique bracket encountered).
    """
    # The LLM text has repeated "[2]" references
    text = (
        "This sentence has [2]. Another mention of [2]. And yet another [2]."
    )

    raw_citations = extract_citations(text)
    # We expect 3 bracket occurrences, all rawIndex=2
    assert len(raw_citations) == 3
    for cit in raw_citations:
        assert cit.index == 2  # the LLM wrote `[2]` each time

    # Reassign them in ascending order
    new_text, new_citations = reassign_citations_in_order(text, raw_citations)

    # The final text should have the *same* bracket each time (e.g. `[1],[1],[1]`)
    # because there's only one unique oldRef = 2, which gets mapped to newIndex=1
    assert (
        new_text.count("[1]") == 3
    ), f"Expected all references to become [1], got: {new_text}"

    # And the new_citations should all share index=1
    for cit in new_citations:
        assert (
            cit.index == 1
        ), f"Expected repeated bracket index=1, got: {cit.index}"
        # Also confirm rawIndex=2 for all occurrences
        assert cit.rawIndex == 2

    mapped = map_citations_to_sources(new_citations, empty_aggregate)
    # out-of-range => placeholders
    for mc in mapped:
        assert mc.sourceType is None
        assert mc.id is None


def test_repeated_bracket_ref_with_two_values(small_aggregate):
    """
    Tests a scenario where the text references [3], [3], [1], [3].
    We want all the [3] occurrences to remain the same final bracket,
    and the [1] to remain or become [1] in ascending order.

    The order we see them: oldRef=3, oldRef=3, oldRef=1, oldRef=3
    The unique old refs are {1,3}, so final brackets might map:
      oldRef=1 => newRef=1
      oldRef=3 => newRef=2
    So the final text might say: [2], [2], [1], [2]
    or if the code sorts them ascending by the numeric oldRef, then
    oldRef=1 => newRef=1, oldRef=3 => newRef=2
    """
    text = (
        "First mention is [3], second mention also [3], "
        "then we have [1], and again [3]."
    )
    raw_citations = extract_citations(text)
    # The LLM has bracket #3 in positions 1,2,4; bracket #1 in position 3
    assert len(raw_citations) == 4

    new_text, new_cits = reassign_citations_in_order(text, raw_citations)
    # The code typically enumerates unique brackets in ascending order by oldRef, i.e. 1 then 3.
    # So oldRef=1 => newIndex=1, oldRef=3 => newIndex=2
    # Then final text becomes: [2], [2], [1], [2]
    # We can confirm that the final text has two bracket numbers total, one for oldRef=1, one for oldRef=3
    bracket_matches = [m.group() for m in re.finditer(r"\[\d+\]", new_text)]
    unique_brackets = set(bracket_matches)
    assert (
        len(unique_brackets) == 2
    ), "Expected exactly 2 bracket values in final text. Got: " + str(
        unique_brackets
    )

    # Check that oldRef=3 => newIndex=2 for all occurrences, oldRef=1 => newIndex=1
    found_1 = [c for c in new_cits if c.rawIndex == 1]
    found_3 = [c for c in new_cits if c.rawIndex == 3]
    assert (
        len(found_1) == 1
    ), f"Expected exactly one bracket occurrence for oldRef=1, got {len(found_1)}"
    assert (
        len(found_3) == 3
    ), f"Expected 3 bracket occurrences for oldRef=3, got {len(found_3)}"
    assert all(
        c.index == found_1[0].index for c in found_1
    ), "All oldRef=1 must share the same final index"
    assert all(
        c.index == found_3[0].index for c in found_3
    ), "All oldRef=3 must share the same final index"

    mapped = map_citations_to_sources(new_cits, small_aggregate)
    # bracket #1 => chunk1, bracket #2 => chunk2 (for example), or it might skip
    # The key is that repeated references to oldRef=3 all map to the same chunk or placeholders.


def test_same_bracket_in_non_sequential_text():
    """
    Confirm that repeated bracket references do not get incorrectly
    assigned multiple new bracket numbers if they appear out of order in the text:
      e.g. [8] ... [2] ... [8] ... [8]
    We want all [8] => newIndex=2 (or something) consistently, not [2], [3], [4].
    """
    text = "We have [8] here, then [2], back to [8], and one more [8]."
    raw_cits = extract_citations(text)
    # Expect 4 bracket references total
    # rawIndex=8 for references #1, #3, #4, and rawIndex=2 for #2
    assert len(raw_cits) == 4

    new_text, new_cits = reassign_citations_in_order(text, raw_cits)
    # Typically you might get two unique oldRefs = {2,8}, so oldRef=2 => newRef=1, oldRef=8 => newRef=2
    # Or if you sort them in the order they appear in the text, it might do oldRef=8 => newRef=1, oldRef=2 => newRef=2.
    # The crucial point: the 3 occurrences of oldRef=8 all share the same newIndex.

    brackets_list = re.findall(r"\[\d+\]", new_text)
    # There should be exactly 2 distinct bracket numbers in the final text
    # The 3 mentions of oldRef=8 => same bracket, and the single mention of oldRef=2 => the other bracket
    unique_brackets = set(brackets_list)
    assert (
        len(unique_brackets) == 2
    ), f"Expected 2 unique brackets, got: {unique_brackets}"

    # Inside new_cits, oldRef=8 should have the same newIndex across all occurrences
    old8_cits = [c for c in new_cits if c.rawIndex == 8]
    assert len(old8_cits) == 3, "Expected 3 mentions referencing oldRef=8"
    first_new_index = old8_cits[0].index
    for c in old8_cits:
        assert (
            c.index == first_new_index
        ), "All oldRef=8 must share the same final bracket index"

    old2_cits = [c for c in new_cits if c.rawIndex == 2]
    assert (
        len(old2_cits) == 1
    ), "Expected exactly one mention referencing oldRef=2"

    # That one mention has a different bracket index from the oldRef=8 group
    assert old2_cits[0].index != first_new_index


def test_three_unique_brackets_with_duplicates():
    """
    A final stress test with multiple bracket references repeated, e.g.:
      [3], [10], [3], [10], [3], [4], [10]
    We want 3 unique oldRefs => 3,4,10 => 3 final bracket numbers, each reused consistently.
    """
    text = (
        "We see bracket [3], then bracket [10], then again bracket [3], "
        "yet again [10], plus a third time [3], now a new bracket [4], "
        "and finally bracket [10]."
    )
    raw = extract_citations(text)
    # oldRef=3 repeated 3 times, oldRef=10 repeated 3 times, oldRef=4 repeated once
    assert len(raw) == 7

    new_text, new_cits = reassign_citations_in_order(text, raw)
    # Should end up with 3 distinct final bracket references total, each repeated as needed.
    # Possibly oldRef=3 => newRef=1, oldRef=4 => newRef=2, oldRef=10 => newRef=3
    # or any consistent mapping that yields exactly 3 final bracket numbers.

    bracket_list = re.findall(r"\[\d+\]", new_text)
    unique_brackets = sorted(set(bracket_list))
    # We expect exactly 3 unique bracket labels in final text:
    assert (
        len(unique_brackets) == 3
    ), f"Expected 3 distinct bracket values, got {unique_brackets}"

    # Confirm each oldRef is consistently re-labeled:
    old3 = [c.index for c in new_cits if c.rawIndex == 3]
    assert (
        len(set(old3)) == 1
    ), "All references to rawIndex=3 must share the same newIndex"

    old4 = [c.index for c in new_cits if c.rawIndex == 4]
    assert (
        len(set(old4)) == 1
    ), "All references to rawIndex=4 must share the same newIndex"

    old10 = [c.index for c in new_cits if c.rawIndex == 10]
    assert (
        len(set(old10)) == 1
    ), "All references to rawIndex=10 must share the same newIndex"

    # That’s the main correctness check. We can map them to actual aggregator results if we had them, but this suffices.


@pytest.fixture
def mock_aggregator_results():
    """
    Return a small AggregateSearchResult with multiple items
    in a known order. We'll pretend the aggregator indexes them
    as 1..N in this same order.
    """
    chunk1 = ChunkSearchResult(
        id=generate_id("chunk-1"),
        document_id=generate_id("doc-1"),
        owner_id=None,
        collection_ids=[],
        score=0.88,
        text="Chunk #1 text",
        metadata={"title": "Doc1.pdf"},
    )
    chunk2 = ChunkSearchResult(
        id=generate_id("chunk-2"),
        document_id=generate_id("doc-2"),
        owner_id=None,
        collection_ids=[],
        score=0.77,
        text="Chunk #2 text",
        metadata={"title": "Doc2.pdf"},
    )
    web1 = WebSearchResult(
        title="Web #1 Title",
        link="http://example.com/web1",
        snippet="Web #1 snippet",
        position=1,
    )
    web2 = WebSearchResult(
        title="Web #2 Title",
        link="http://example.com/web2",
        snippet="Web #2 snippet",
        position=2,
    )
    graph1 = GraphSearchResult(
        content=GraphEntityResult(name="x", description="y"),
        result_type="entity",
        metadata={"graph_key": "graphVal"},
        score=1.0,
    )

    agg = AggregateSearchResult(
        chunk_search_results=[chunk1, chunk2],
        graph_search_results=[graph1],
        web_search_results=[web1, web2],
        context_document_results=[],
    )
    return agg


def test_end_to_end_citation_remapping(mock_aggregator_results):
    """
    1) We define the text that the LLM hypothetically produced.
       It references aggregator item #3, #1, #5, #1, #4 in random order.
       But let's pretend the aggregator only has 5 total items:
         1 -> chunk1
         2 -> chunk2
         3 -> graph1
         4 -> web1
         5 -> web2
    2) We'll run extract_citations, reassign_citations_in_order, map_citations_to_sources
    3) Confirm the final text has bracket references [1..N] in ascending order of *appearance*,
       or by old ref sorted, whichever your system does, and that we unify repeated references properly.
    """
    collector = SearchResultsCollector()
    collector.add_aggregate_result(mock_aggregator_results)

    # The aggregator has 5 items: chunk1->(1), chunk2->(2), graph1->(3), web1->(4), web2->(5)
    # We'll create an LLM final text that references them in a weird order:
    #   oldRef=3, oldRef=1, oldRef=5, oldRef=1, oldRef=4
    # Notice we repeated oldRef=1

    raw_llm_text = (
        "Major updates: The Graph item is mentioned [3]. Then we mention chunk1 [1]. "
        "Oh, we also have web2 [5]. Wait, chunk1 again [1]. Finally web1 [4]."
    )

    # 1) Extract bracket references
    raw_citations = extract_citations(raw_llm_text)
    assert len(raw_citations) == 5

    # 2) Re-label them in ascending bracket order for display,
    #    but store the original aggregator index in rawIndex
    new_text, reassigned_citations = reassign_citations_in_order(
        raw_llm_text, raw_citations
    )

    # 3) Map citations by using the aggregator's oldRef => aggregator #.
    #    i.e. we look up rawIndex in the collector
    final_mapped = map_citations_to_collector(reassigned_citations, collector)

    # 4) Let's check that repeated references map properly
    #    Specifically, if oldRef=1 is repeated, they should share the same final bracket index
    #    and map to aggregator item #1 (which is chunk1).
    # We'll check bracket index => aggregator item

    # For convenience, let’s just build a small helper:
    def citation_summary(c: Citation):
        return {
            "finalIndex": c.index,
            "rawIndex": getattr(
                c, "rawIndex", c.rawIndex
            ),  # Some code calls it oldIndex
            "sourceType": c.sourceType,
            "docId": c.document_id or "",
            "title": (c.metadata.get("title") if c.metadata else ""),
        }

    mapped_summaries = [citation_summary(c) for c in final_mapped]
    print("Mapped Summaries:\n", mapped_summaries)

    # Let’s just do *some* asserts. For example:
    # - oldRef=1 => chunk1 => sourceType="chunk", doc_id="doc-1"
    # - oldRef=3 => graph => sourceType="graph"
    # - oldRef=4 => web => "Web #1 Title"
    # - oldRef=5 => web => "Web #2 Title"
    # Because we repeated oldRef=1, we want both references to have the same final bracket index
    # and the same aggregator item.

    # Group by rawIndex
    from collections import defaultdict

    grouped = defaultdict(list)
    for c in final_mapped:
        grouped[c.rawIndex].append(c)

    # oldRef=1 => chunk1
    print("grouped = ", grouped)
    old1_cits = grouped[1]
    print("old1_cits = ", old1_cits)
    assert len(old1_cits) == 2, "We repeated oldRef=1 exactly twice"
    # They should share same final 'index' if your code unifies repeated references
    final_idx_set = {c.index for c in old1_cits}
    assert (
        len(final_idx_set) == 1
    ), "All references to oldRef=1 must share the same final bracket index"
    # They should map to chunk1 => doc-1
    for c in old1_cits:
        assert c.sourceType == "chunk"
        assert c.document_id == str(generate_id("doc-1"))

    # oldRef=3 => graph
    old3_cits = grouped[3]
    assert len(old3_cits) == 1
    assert old3_cits[0].sourceType == "graph"

    # oldRef=4 => web => Web #1 Title
    old4_cits = grouped[4]
    assert len(old4_cits) == 1
    assert old4_cits[0].sourceType == "web"
    assert old4_cits[0].metadata["title"] == "Web #1 Title"

    # oldRef=5 => web => Web #2 Title
    old5_cits = grouped[5]
    assert len(old5_cits) == 1
    assert old5_cits[0].sourceType == "web"
    assert old5_cits[0].metadata["title"] == "Web #2 Title"

    # 5) Finally, ensure the final text “new_text” has the bracket references in ascending
    #    final index for each unique oldRef, and all repeated references for oldRef=1 share the same bracket.
    # E.g. if your code enumerates references by first appearance, the final text might do:
    #   "Major updates: The Graph item is mentioned [1]. Then we mention chunk1 [2]."
    #   "Oh, we also have web2 [3]. Wait, chunk1 again [2]. Finally web1 [4]."
    # We can confirm that the text *indeed* has exactly 4 distinct bracket numbers in total:
    import re

    bracket_values = re.findall(r"\[(\d+)\]", new_text)
    # We expect 5 occurrences total (matching the 5 references),
    # but the bracket labels might be something like 1,2,3,2,4 => 4 distinct bracket numbers
    # with the second bracket repeated. Just check the pattern you expect:
    assert len(bracket_values) == 5
    # The repeated oldRef=1 occurrences => same new bracket
    # so we expect a repeated bracket number. For instance if bracket_values is [2,1,4,1,3],
    # it depends on how your code sorts them. The key is that index(1) repeats exactly twice.

    # (Optional) If you want a more strict check that the final text is exactly what you expect,
    # you can do an exact string compare:
    #   assert new_text == "Major updates: The Graph item is mentioned [1]. Then we mention chunk1 [2]. ...
    # But that depends on the precise logic of your assignment algorithm.

    print("Final text:\n", new_text)
    print("Test passed successfully!")


@pytest.fixture
def ordered_aggregate():
    """
    Returns an AggregateSearchResult with 5 total items in
    the order: [chunk1, chunk2, graph1, web1, web2].
    We'll rely on that ordering as aggregator #1..#5.
    """
    # 1) Two chunk results
    chunk1 = ChunkSearchResult(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        owner_id=None,
        collection_ids=[],
        score=0.88,
        text="Chunk #1 text",
        metadata={"doc": "chunk1"},
    )
    chunk2 = ChunkSearchResult(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        owner_id=None,
        collection_ids=[],
        score=0.66,
        text="Chunk #2 text",
        metadata={"doc": "chunk2"},
    )
    # 2) One Graph result
    graph_entity = GraphEntityResult(
        id=uuid.uuid4(),
        name="GraphEntityName",
        description="GraphEntityDesc",
    )
    graph1 = GraphSearchResult(
        content=graph_entity,
        result_type="entity",
        score=0.99,
        metadata={"graph_key": "graphVal"},
    )
    # 3) Two Web results
    web1 = WebSearchResult(
        title="Web1 Title",
        link="http://example.com/web1",
        snippet="Snippet for web1",
        position=1,
    )
    web2 = WebSearchResult(
        title="Web2 Title",
        link="http://example.com/web2",
        snippet="Snippet for web2",
        position=2,
    )

    agg = AggregateSearchResult(
        chunk_search_results=[chunk1, chunk2],
        graph_search_results=[graph1],
        web_search_results=[web1, web2],
        context_document_results=[],
    )
    return agg


def test_end_to_end_mocked_aggregator(ordered_aggregate):
    """
    Demonstrates:
     1) We add aggregator items in a known order => aggregator #1 => chunk1, #2 => chunk2, #3 => graph1, #4 => web1, #5 => web2.
     2) The LLM text references them in random bracket order, e.g. [3],[1],[5],[1],[4].
     3) We reassign => bracket [1],[2],[3],[2],[4] and confirm that repeated references to oldRef=1 remain the same bracket.
     4) Finally, map them to aggregator items => bracket [2] => aggregator #1 => chunk1, bracket [3] => aggregator #5 => web2, etc.
    """
    collector = SearchResultsCollector()

    # Step 1: add the entire "ordered_aggregate" in a single pass
    # This ensures aggregator #1..#5 are assigned in that exact order
    collector.add_aggregate_result(ordered_aggregate)
    # We expect the collector results_in_order to be:
    #   [("chunk", chunk1, 1), ("chunk", chunk2, 2), ("graph", graph1, 3), ("web", web1, 4), ("web", web2, 5)]

    # Step 2: LLM text references them out of order: aggregator #3, #1, #5, #1, #4
    raw_text = (
        "We mention aggregator #3 first [3], then aggregator #1 [1], "
        "then aggregator #5 [5], then aggregator #1 again [1], "
        "finally aggregator #4 [4]."
    )

    # 2a) extract brackets
    raw_cits = extract_citations(raw_text)
    # Should find 5 references: oldRef=3,1,5,1,4
    assert len(raw_cits) == 5

    # 2b) reassign => e.g. bracket #1 => oldRef=3, bracket #2 => oldRef=1, bracket #3 => oldRef=5, bracket #2 => oldRef=1 again, bracket #4 => oldRef=4
    new_text, new_cits = reassign_citations_in_order(raw_text, raw_cits)

    # 2c) confirm that repeated oldRef=1 is assigned the same final bracket number each time
    # Let's gather them by rawIndex
    from collections import defaultdict

    bucket = defaultdict(list)
    for c in new_cits:
        bucket[c.rawIndex].append(c.index)

    # oldRef=1 => repeated => should share the same newIndex
    indexes_for_1 = set(bucket[1])
    assert (
        len(indexes_for_1) == 1
    ), f"All references to oldRef=1 must unify, found indexes: {indexes_for_1}"

    # Step 3: map to aggregator items
    final_mapped = map_citations_to_collector(new_cits, collector)

    # aggregator #3 => bracket #1 => "graph"
    # aggregator #1 => bracket #2 => "chunk"
    # aggregator #5 => bracket #3 => "web"
    # aggregator #4 => bracket #4 => "web"
    # repeated aggregator #1 => bracket #2 => chunk again

    # Let's see them in print
    for i, fc in enumerate(final_mapped, start=1):
        print(
            f"Final citation #{i} => bracket {fc.index} => aggregator #{fc.rawIndex}"
        )
        print(" sourceType=", fc.sourceType)
        print(" docID=", fc.document_id)
        print(" text=", fc.text)
        print(" metadata=", fc.metadata)
        print("-----")

    # We'll do a minimal check that aggregator #3 => graph
    # Find the mapped citation(s) with rawIndex=3
    cit_for3 = [fc for fc in final_mapped if fc.rawIndex == 3]
    assert len(cit_for3) == 1
    assert cit_for3[0].sourceType == "graph"

    # aggregator #1 => chunk => repeated
    cit_for1 = [fc for fc in final_mapped if fc.rawIndex == 1]
    assert len(cit_for1) == 2
    for c in cit_for1:
        assert c.sourceType == "chunk"

    # aggregator #5 => web
    cit_for5 = [fc for fc in final_mapped if fc.rawIndex == 5]
    assert len(cit_for5) == 1
    assert cit_for5[0].sourceType == "web"

    # aggregator #4 => web
    cit_for4 = [fc for fc in final_mapped if fc.rawIndex == 4]
    assert len(cit_for4) == 1
    assert cit_for4[0].sourceType == "web"

    print("Re-labeled text:\n", new_text)
    # e.g. => "We mention aggregator #3 first [1], then aggregator #1 [2], then aggregator #5 [3], aggregator #1 again [2], aggregator #4 [4]."

    # Confirm repeated bracket for aggregator #1
    count_b2 = new_text.count("[2]")
    assert (
        count_b2 == 2
    ), f"Expected aggregator #1 references to unify to bracket [2], found text: {new_text}"

    print("Test end_to_end_mocked_aggregator passed successfully!")


def test_hybrid_aggregation_format():
    """
    Demonstrates combining chunk, graph, and web results in a single
    AggregateSearchResult, adding them to the collector, and verifying
    the LLM-format output includes each in the correct 'Vector Search Results:',
    'Graph Search Results:', and 'Web Search Results:' sections.
    """
    collector = SearchResultsCollector()

    # Build an all-in-one AggregateSearchResult
    chunkA = ChunkSearchResult(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        owner_id=None,
        collection_ids=[],
        score=0.80,
        text="Chunk A text",
        metadata={"title": "DocA"},
    )
    graphA = GraphSearchResult(
        content=GraphEntityResult(
            name="GraphEntity", description="Some entity in the KG"
        ),
        result_type="entity",
        metadata={"graphKey": "graphVal"},
        score=0.90,
    )
    webA = WebSearchResult(
        title="Some Web Page",
        link="https://example.com/page",
        snippet="An example snippet",
        position=1,
    )

    agg = AggregateSearchResult(
        chunk_search_results=[chunkA],
        graph_search_results=[graphA],
        web_search_results=[webA],
        context_document_results=[],
    )

    # Add to collector => aggregator #1 => chunk, #2 => graph, #3 => web
    collector.add_aggregate_result(agg)

    # 2) Call format_search_results_for_llm
    from core.base import format_search_results_for_llm

    llm_text = format_search_results_for_llm(agg, collector)

    # Check that we get "Vector Search Results:", "Graph Search Results:", "Web Search Results:"
    assert "Vector Search Results:" in llm_text
    assert "Graph Search Results:" in llm_text
    assert "Web Search Results:" in llm_text

    # aggregator #1 => chunk => "Chunk A text"
    assert "Source [1]:" in llm_text
    assert "Chunk A text" in llm_text

    # aggregator #2 => graph => "GraphEntity"
    assert "Source [2]:" in llm_text
    assert "GraphEntity" in llm_text
    assert "Some entity in the KG" in llm_text

    # aggregator #3 => web => "Some Web Page"
    assert "Source [3]:" in llm_text
    assert "Some Web Page" in llm_text
    assert "An example snippet" in llm_text

    print("test_hybrid_aggregation_format passed successfully!")


def test_collector_multiple_calls_with_small_aggregate(small_aggregate):
    """
    Demonstrate calling collector.add_aggregate_result() multiple times
    and confirm aggregator indexes continue incrementing.
    """
    collector = SearchResultsCollector()

    # First call: aggregator #1..#3 => chunk1, chunk2, chunk3
    collector.add_aggregate_result(small_aggregate)

    # Now aggregator #1 => doc-1, aggregator #2 => doc-2, aggregator #3 => doc-3
    all_items = collector.get_all_results()
    assert len(all_items) == 3
    # Confirm the aggregator assigns them in the chunk-search order:
    #   chunk1 => aggregator #1 => doc-1
    #   chunk2 => aggregator #2 => doc-2
    #   chunk3 => aggregator #3 => doc-3
    (stype1, obj1, idx1) = all_items[0]
    assert stype1 == "chunk"
    assert idx1 == 1
    assert str(obj1.document_id) == str(generate_id("doc-1"))

    (stype2, obj2, idx2) = all_items[1]
    assert stype2 == "chunk"
    assert idx2 == 2
    assert str(obj2.document_id) == str(generate_id("doc-2"))

    (stype3, obj3, idx3) = all_items[2]
    assert stype3 == "chunk"
    assert idx3 == 3
    assert str(obj3.document_id) == str(generate_id("doc-3"))

    # If we add more items again, they'd become aggregator #4.. etc.
    # This checks that multiple calls do not reset the index.


def test_collector_out_of_range_with_small_aggregate(small_aggregate):
    """
    If the LLM references [5] but we only have aggregator items #1..#3,
    map_citations_to_collector() should produce sourceType="unknown".
    """
    collector = SearchResultsCollector()
    collector.add_aggregate_result(small_aggregate)
    # aggregator #1 => doc-1, #2 => doc-2, #3 => doc-3

    text = "Here is an out-of-range bracket [5]."
    raw_cits = extract_citations(text)
    # => bracket #5
    new_text, new_cits = reassign_citations_in_order(text, raw_cits)
    # The final text might have [1] if it’s the first unique bracket, or remain [5] if your logic sees them as already in ascending order
    mapped = map_citations_to_collector(new_cits, collector)

    # aggregator #5 doesn’t exist => sourceType="unknown"
    # So we confirm the mapped citation is unknown
    assert len(mapped) == 1
    assert mapped[0].sourceType in (None, "unknown")


def test_collector_repeated_same_aggregator_with_small_aggregate(
    small_aggregate,
):
    """
    If the LLM text references aggregator #2 multiple times, e.g. [2], [2], [2],
    then after reassign_citations_in_order, all should unify to the same final bracket,
    and map to chunk2 => doc-2 in aggregator.
    """
    collector = SearchResultsCollector()
    collector.add_aggregate_result(small_aggregate)
    # aggregator #1 => doc-1, #2 => doc-2, #3 => doc-3

    text = "First mention [2], second mention [2], third mention [2]."
    raw_cits = extract_citations(text)
    # raw_cits => bracket #2 repeated thrice
    new_text, new_cits = reassign_citations_in_order(text, raw_cits)
    # Possibly ends up "[1], [1], [1]" in the final text if bracket #2 is the first unique reference.
    mapped = map_citations_to_collector(new_cits, collector)

    # All references => aggregator #2 => doc-2
    for c in mapped:
        assert c.rawIndex == 2  # old aggregator index
        assert c.sourceType == "chunk"
        assert str(c.document_id) == str(generate_id("doc-2"))
        # or check c.metadata["title"] == "Doc2.pdf"


def test_collector_mixed_references_small_aggregate(small_aggregate):
    """
    Suppose the LLM references aggregator #3, #1, #3, #2 in random order.
    That means bracket [3] => chunk #3 doc-3, bracket [1] => chunk #1 doc-1, bracket [2] => doc-2, etc.
    Then after reassign, we confirm final text has them in ascending bracket order
    while the mapped citations remain correct.
    """
    collector = SearchResultsCollector()
    collector.add_aggregate_result(small_aggregate)
    # aggregator #1 => doc-1, #2 => doc-2, #3 => doc-3

    text = "We mention aggregator #3 [3], then aggregator #1 [1], again aggregator #3 [3], and aggregator #2 [2]."
    raw_cits = extract_citations(text)
    # => brackets #3, #1, #3, #2 in that order
    new_text, new_cits = reassign_citations_in_order(text, raw_cits)
    # Possibly:
    #  oldRef=3 => newIndex=1
    #  oldRef=1 => newIndex=2
    #  oldRef=3 => newIndex=1 (again)
    #  oldRef=2 => newIndex=3
    # So final text might become:
    #   "We mention aggregator #3 [1], then aggregator #1 [2], again aggregator #3 [1], and aggregator #2 [3]."

    mapped = map_citations_to_collector(new_cits, collector)
    # aggregator #3 => doc-3
    # aggregator #1 => doc-1
    # aggregator #2 => doc-2

    # Check grouping
    from collections import defaultdict

    grouped = defaultdict(list)
    for c in mapped:
        grouped[c.rawIndex].append(c)

    # aggregator #3 => doc-3
    cits_for_3 = grouped[3]
    assert len(cits_for_3) == 2, "We used aggregator #3 twice."
    for c in cits_for_3:
        assert str(c.document_id) == str(generate_id("doc-3"))

    # aggregator #1 => doc-1
    cits_for_1 = grouped[1]
    assert len(cits_for_1) == 1
    assert str(cits_for_1[0].document_id) == str(generate_id("doc-1"))

    # aggregator #2 => doc-2
    cits_for_2 = grouped[2]
    assert len(cits_for_2) == 1
    assert str(cits_for_2[0].document_id) == str(generate_id("doc-2"))

    # Optional check final text bracket pattern
    # e.g. bracket references => [1], [2], [1], [3] in that order
    import re

    final_brackets = re.findall(r"\[(\d+)\]", new_text)
    assert len(final_brackets) == 4
    # The references to oldRef=3 unify to the same bracket number each time.
