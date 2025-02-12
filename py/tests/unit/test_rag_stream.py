import asyncio
import re

import pytest


# ----------------------------------------------------------------------
# Mock SSE Generator
# ----------------------------------------------------------------------
async def mock_rag_sse_generator(chunks):
    """
    This is a simplified version of your streaming RAG SSE generator.
    It demonstrates how you'd split tokens, detect bracket references,
    and emit SSE lines.

    Instead of calling the actual LLM, we simply iterate over a list
    of string "chunks" that you pass in for test simulation.
    """
    bracket_pattern = re.compile(r"\[\s*(\d+)\s*\]")
    partial_buffer = ""
    parse_position = 0
    seen_brackets = set()

    # 1) Emit a "search_results" event as you do initially
    search_evt = {
        "id": "run_1",
        "object": "rag.search_results",
        "data": {"dummy_search_data": "example"},
    }
    yield _format_sse_event("search_results", search_evt)

    # 2) Stream each chunk as a "message" SSE event
    for token_text in chunks:
        old_length = len(partial_buffer)  # might be used if you prefer
        partial_buffer += token_text

        # Check for bracket references from parse_position to end
        for match in bracket_pattern.finditer(partial_buffer, parse_position):
            bracket_str = match.group(1)
            bracket_num = int(bracket_str)
            if bracket_num not in seen_brackets:
                seen_brackets.add(bracket_num)
                # Emit a "citation" SSE event
                citation_evt = {
                    "id": f"cit_{bracket_num}",
                    "object": "rag.citation",
                    "data": {"rawIndex": bracket_num},
                }
                yield _format_sse_event("citation", citation_evt)

            # Advance parse_position to avoid re‐matching the same bracket
            parse_position = match.end()

        # Now emit the partial text chunk as a "message" SSE event
        message_evt = {
            "id": "msg_1",
            "object": "thread.message.delta",
            "delta": {
                "content": [
                    {
                        "type": "text",
                        "text": {"value": token_text, "annotations": []},
                    }
                ]
            },
        }
        yield _format_sse_event("message", message_evt)

    # 3) After all chunks, do the final re‐labeling & "final_answer" event
    #    For brevity, we'll skip the re‐labeling here. In your real code,
    #    you do partial_buffer -> extract -> reassign -> map. We'll just
    #    pretend there's some final text.

    final_ans_evt = {
        "id": "msg_final",
        "object": "rag.final_answer",
        "generated_answer": partial_buffer,
        "citations": [],  # would be your mapped citations
    }
    yield _format_sse_event("final_answer", final_ans_evt)

    # 4) Indicate "done"
    yield "event: done\ndata: [DONE]\n\n"


def _format_sse_event(event_name: str, payload: dict) -> str:
    """
    Helper to produce a single SSE event as a multiline string.
    This matches your `_yield_sse_event` approach, except we're
    returning a single string rather than yielding line-by-line.
    """
    import json

    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sse_no_brackets():
    """
    Verify that if we never see a bracket reference in any chunk,
    we never emit a 'citation' event.
    """
    chunks = [
        "Hello, this is a test. ",
        "We have no bracket references here. ",
        "Just more plain text.",
    ]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    # We should see:
    #   1) search_results
    #   2) message events for each chunk
    #   3) final_answer
    #   4) done
    # No 'citation' events
    citation_events = [e for e in events if e.startswith("event: citation")]
    assert (
        len(citation_events) == 0
    ), f"Unexpected citations found: {citation_events}"

    # We do expect "search_results", "message", "final_answer", "done"
    assert any("search_results" in e for e in events)
    assert any("final_answer" in e for e in events)
    assert any("done" in e for e in events)


@pytest.mark.asyncio
async def test_sse_single_bracket_one_chunk():
    """
    If we have a single bracket reference [1] in one chunk,
    we should get exactly one 'citation' event.
    """
    chunks = ["Aristotle was an Ancient Greek philosopher [1]."]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    # Check citations
    citation_events = [e for e in events if e.startswith("event: citation")]
    assert (
        len(citation_events) == 1
    ), f"Expected 1 citation event, got: {citation_events}"
    assert (
        '"rawIndex": 1' in citation_events[0]
    ), "The bracket was [1] => rawIndex=1"

    # Check messages
    message_events = [e for e in events if e.startswith("event: message")]
    assert (
        len(message_events) == 1
    ), "We have exactly 1 chunk => 1 'message' event"

    # Check final_answer
    final_answer_events = [
        e for e in events if e.startswith("event: final_answer")
    ]
    assert (
        len(final_answer_events) == 1
    ), "We expect exactly one 'final_answer' event at the end."


@pytest.mark.asyncio
async def test_sse_bracket_split_across_chunks():
    """
    The bracket [1] is split across multiple chunks:
    e.g. chunk1 => "Aristotle ["
         chunk2 => "1"
         chunk3 => "]."
    Once the entire substring "[1]" is in partial_buffer,
    we should get a single citation event.
    """
    chunks = ["Aristotle [", "1", "]. He was a philosopher."]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    # We want to ensure we eventually see the bracket reference once it's completed
    citation_events = [e for e in events if e.startswith("event: citation")]
    assert (
        len(citation_events) == 1
    ), f"Expected exactly 1 citation event, got: {citation_events}"
    assert '"rawIndex": 1' in citation_events[0], "Should detect bracket #1"

    # We also have 3 message events for the 3 chunks
    message_events = [e for e in events if e.startswith("event: message")]
    assert len(message_events) == 3, "One message event per chunk"

    # Confirm final answer
    final_ans = [e for e in events if e.startswith("event: final_answer")]
    assert len(final_ans) == 1


@pytest.mark.asyncio
async def test_sse_repeated_bracket_references():
    """
    If the chunk text has repeated references to the same bracket, e.g. [2], [2], [2],
    we want exactly one 'citation' event for bracket #2 the first time it appears,
    not multiple times.
    """
    chunks = [
        "Aristotle is mentioned [2]. Another line with the same bracket [2].",
        "And yet again [2] at the end!",
    ]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    citation_events = [e for e in events if e.startswith("event: citation")]
    assert (
        len(citation_events) == 1
    ), f"Repeated bracket #2 => only 1 citation event, got: {citation_events}"
    assert '"rawIndex": 2' in citation_events[0], "Should detect bracket #2"

    # We have 2 chunks => 2 message events
    message_events = [e for e in events if e.startswith("event: message")]
    assert len(message_events) == 2, "One message event per chunk"

    final_ans = [e for e in events if e.startswith("event: final_answer")]
    assert len(final_ans) == 1


@pytest.mark.asyncio
async def test_sse_out_of_order_brackets():
    """
    If the text has bracket references out of order, e.g. [3], [1], [3], [2],
    we still see each unique bracket once in the citation events, in the order they appear.
    """
    chunks = [
        "We mention bracket [3], then bracket [1]. Next chunk is [3] again, oh, now [2]."
    ]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    # We'll parse them from the SSE stream
    citation_events = [e for e in events if e.startswith("event: citation")]
    # Expect 3 unique brackets: 3, 1, 2
    # The second time we see [3] => no new event
    assert len(citation_events) == 3, f"Got: {citation_events}"
    # Check the rawIndex in order
    raw_indexes = []
    for ce in citation_events:
        # e.g. 'event: citation\ndata: {"id":"cit_3","object":"rag.citation","data":{"rawIndex":3}}\n\n'
        match = re.search(r'"rawIndex":\s*(\d+)', ce)
        if match:
            raw_indexes.append(int(match.group(1)))

    # We expect 3 => 1 => 2, in that order, matching their first appearances
    assert raw_indexes == [
        3,
        1,
        2,
    ], f"Unexpected bracket detection order: {raw_indexes}"

    message_events = [e for e in events if e.startswith("event: message")]
    assert len(message_events) == 1, "We only had 1 chunk"


@pytest.mark.asyncio
async def test_sse_multiple_chunks_mixed_split_brackets():
    """
    A more advanced scenario where partial bracket references
    appear across chunk boundaries, and we also have an already-complete bracket
    in the same or different chunk.

    e.g. chunk1 => "Aristotle has [1] and an incomplete bracket [2"
        chunk2 => "] plus more text [3]."
    We want 2 new citations total: #1 and #2 and #3. Actually 3 distinct ones.
    """
    chunks = [
        "Aristotle has [1] and an incomplete bracket [2",
        "] plus more text [3].",
    ]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    citation_events = [e for e in events if e.startswith("event: citation")]
    # We expect bracket #1, bracket #2, bracket #3
    # Bracket #2 is split across chunk1, chunk2
    assert (
        len(citation_events) == 3
    ), f"Expected brackets 1,2,3 => 3 events, got {citation_events}"

    # Verify the bracket IDs
    found = []
    for ce in citation_events:
        m = re.search(r'"rawIndex":\s*(\d+)', ce)
        if m:
            found.append(int(m.group(1)))
    found.sort()
    assert found == [1, 2, 3], f"Got bracket IDs: {found}"


@pytest.mark.asyncio
async def test_sse_no_final_bracket_closure():
    """
    If a bracket never closes, e.g. we see "[4" but never the ']' character,
    we should NOT emit a citation event for bracket #4.
    """
    chunks = ["First chunk has bracket [4", " but we never close it"]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    # We expect 0 citations
    citation_events = [e for e in events if "event: citation" in e]
    assert (
        len(citation_events) == 0
    ), "We never completed [4], so no citation event."

    # We do have 2 message events, 1 final_answer, 1 done
    message_events = [e for e in events if "event: message" in e]
    assert len(message_events) == 2
    final_events = [e for e in events if "event: final_answer" in e]
    assert len(final_events) == 1


@pytest.mark.asyncio
async def test_sse_duplicate_brackets_split_across_chunks():
    """
    If the text references the same bracket [5] in partial form across multiple chunks,
    e.g. chunk1 => "Aristotle has ["
         chunk2 => "5"
         chunk3 => "] then again ["
         chunk4 => "5"
         chunk5 => "]."
    We only want exactly 1 citation event for bracket #5, once fully recognized the FIRST time.
    The second time [5] is fully recognized, we've already seen bracket #5 => no new citation event.
    """
    chunks = ["Aristotle has [", "5", "] then again [", "5", "]."]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    citation_events = [e for e in events if e.startswith("event: citation")]
    assert len(citation_events) == 1, (
        "Bracket #5 is repeated, but we only want it once. "
        f"Got: {citation_events}"
    )
    assert (
        '"rawIndex": 5' in citation_events[0]
    ), "We recognized bracket #5 once"

    # We have 5 chunks => 5 'message' events
    message_events = [e for e in events if e.startswith("event: message")]
    assert len(message_events) == 5

    final_answer_events = [
        e for e in events if e.startswith("event: final_answer")
    ]
    assert len(final_answer_events) == 1


@pytest.mark.asyncio
async def test_sse_bracket_with_spaces_inside():
    """
    If your bracket pattern includes optional spaces, e.g. [   2   ],
    confirm we still detect bracket #2.
    """
    chunks = ["Aristotle [   2   ] was a polymath."]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    citation_events = [e for e in events if e.startswith("event: citation")]
    assert len(citation_events) == 1, f"Got: {citation_events}"
    assert (
        '"rawIndex": 2' in citation_events[0]
    ), "Detected bracket [2] even with spaces"


@pytest.mark.asyncio
async def test_sse_multiple_brackets_one_chunk():
    """
    A chunk containing multiple bracket references [1], [2], [3].
    We expect 3 citations, each recognized in a single chunk.
    """
    chunk = "Aristotle wrote on many topics [1], including logic [2], and zoology [3]."
    events = []
    async for evt in mock_rag_sse_generator([chunk]):
        events.append(evt)

    citation_events = [e for e in events if e.startswith("event: citation")]
    assert len(citation_events) == 3, f"Got: {citation_events}"
    # order is 1,2,3 in the text
    bracket_nums = []
    for ce in citation_events:
        m = re.search(r'"rawIndex":\s*(\d+)', ce)
        if m:
            bracket_nums.append(int(m.group(1)))
    assert bracket_nums == [
        1,
        2,
        3,
    ], f"Unexpected bracket detection order: {bracket_nums}"


@pytest.mark.asyncio
async def test_sse_complex_mixed():
    """
    A more elaborate test with partial bracket splits, repeated references,
    and normal references all in multiple chunks.
    For example:
      chunk1 => "Aristotle [1], [5], and ["
      chunk2 => "5"
      chunk3 => "] again. Another incomplete [3"
      chunk4 => ". Actually that was completed [3]."
      chunk5 => "Finally we see [2]."
    We'll track events carefully.
    """
    chunks = [
        "Aristotle [1], [5], and [",
        "5",
        "] again. Another incomplete [3",
        ". Actually that was completed [3].",
        "Finally we see [2].",
    ]
    events = []
    async for evt in mock_rag_sse_generator(chunks):
        events.append(evt)

    # Let's gather all "citation" lines
    citation_events = [e for e in events if e.startswith("event: citation")]

    # We expect bracket #1 recognized in chunk1,
    # bracket #5 recognized in chunk1 as well,
    # bracket #5 repeated in chunk2 => no new event,
    # bracket #3 partially in chunk3, completed in chunk4 => single event for bracket #3,
    # bracket #2 in chunk5 => single event for bracket #2
    # So total unique brackets => 1,5,3,2 => 4 citations
    assert len(citation_events) == 4, f"Got citation events: {citation_events}"

    # Verify the bracket IDs
    found = []
    for ce in citation_events:
        m = re.search(r'"rawIndex":\s*(\d+)', ce)
        if m:
            found.append(int(m.group(1)))

    found.sort()
    assert found == [
        1,
        2,
        3,
        5,
    ], f"Unexpected bracket references found: {found}"

    # Also expect 5 message events
    message_events = [e for e in events if e.startswith("event: message")]
    assert len(message_events) == 5, "One per chunk"

    final_answers = [e for e in events if e.startswith("event: final_answer")]
    assert (
        len(final_answers) == 1
    ), "We do a single 'final_answer' event at the end."

    done_evt = [e for e in events if e.startswith("event: done")]
    assert len(done_evt) == 1
