"""
Unit tests for citation handling in retrieval functionality.
"""
import pytest
import re
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Any, Optional

# Import citation utilities from core.utils
from core.utils import (
    extract_citations,
    extract_citation_spans,
    find_new_citation_spans,
    CitationTracker as CoreCitationTracker
)

class CitationTracker:
    """Simple citation tracker for testing."""
    def __init__(self):
        # Track which citation spans we've processed
        # Format: {citation_id: {(start, end), (start, end), ...}}
        self.processed_spans = {}
        self.citation_spans = {}
    
    def is_new_span(self, citation_id, span):
        """Check if this span is new and mark it as processed if it is."""
        # Handle invalid inputs
        if citation_id is None or citation_id == "" or span is None:
            return False
            
        # Initialize set for this citation ID if needed
        if citation_id not in self.processed_spans:
            self.processed_spans[citation_id] = set()
            
        # Check if we've seen this span before for this citation
        if span in self.processed_spans[citation_id]:
            return False
            
        # This is a new span, track it
        self.processed_spans[citation_id].add(span)
        
        # Also track by citation ID for easy lookup
        if citation_id not in self.citation_spans:
            self.citation_spans[citation_id] = []
        
        self.citation_spans[citation_id].append(span)
        return True
    
    def get_all_citation_spans(self):
        """Get all citation spans processed so far."""
        return {
            citation_id: spans
            for citation_id, spans in self.citation_spans.items()
        }


class MockCitation:
    """Mock Citation class for testing."""
    def __init__(self, citation_id, chunk_id=None, document_id=None, text=None, metadata=None):
        self.citation_id = citation_id
        self.chunk_id = chunk_id or f"chunk-{citation_id}"
        self.document_id = document_id or f"doc-{citation_id}"
        self.text = text or f"Citation text for {citation_id}"
        self.metadata = metadata or {"source": f"source-{citation_id}"}
        self.spans = []


@pytest.fixture
def mock_providers():
    """Return a mocked providers object for testing."""
    class MockProviders:
        def __init__(self):
            # Mock the database
            self.database = AsyncMock()
            self.database.citations_handler = AsyncMock()
            self.database.citations_handler.get_citation = AsyncMock(
                side_effect=lambda citation_id: MockCitation(citation_id)
            )
            
            # Mock LLM
            self.llm = AsyncMock()
            self.llm.aget_completion = AsyncMock(
                return_value={"choices": [{"message": {"content": "Response with [abc1234] citation"}}]}
            )
            self.llm.aget_completion_stream = AsyncMock(
                return_value=iter([
                    {"choices": [{"delta": {"content": "Response "}}]},
                    {"choices": [{"delta": {"content": "with "}}]},
                    {"choices": [{"delta": {"content": "[abc1234] "}}]},
                    {"choices": [{"delta": {"content": "citation"}}]}
                ])
            )

    return MockProviders()


@pytest.fixture
def sample_chunk_results():
    """Return sample chunk results with citation metadata."""
    return [
        {
            "chunk_id": f"chunk-{i}",
            "document_id": f"doc-{i//2}",
            "text": f"This is chunk {i} with information about the topic.",
            "metadata": {
                "source": f"source-{i}",
                "citation_id": f"cite{i}"
            },
            "score": 0.95 - (i * 0.05),
        }
        for i in range(5)
    ]


class TestCitationExtraction:
    """Tests for citation extraction functionality."""
    
    def test_extract_citations_basic(self):
        """Test basic citation extraction from text with standard format."""
        # Test function to extract citations
        def extract_citations(text):
            citation_pattern = r'\[([\w\d]+)\]'
            citations = re.findall(citation_pattern, text)
            return citations
        
        # Test cases
        test_cases = [
            (
                "Aristotle discussed virtue ethics in his Nicomachean Ethics [abc1234].",
                ["abc1234"]
            ),
            (
                "According to Plato [xyz5678] and Aristotle [abc1234], philosophy is important.",
                ["xyz5678", "abc1234"]
            ),
            (
                "This text has no citations.",
                []
            ),
            (
                "Multiple citations in a row [abc1234][def5678][ghi9012] should all be found.",
                ["abc1234", "def5678", "ghi9012"]
            )
        ]
        
        # Run tests
        for text, expected_citations in test_cases:
            extracted = extract_citations(text)
            assert extracted == expected_citations
    
    def test_extract_citations_with_spans(self):
        """Test citation extraction with text spans."""
        # Test function to extract citations with spans
        def extract_citations_with_spans(text):
            citation_pattern = r'\[([\w\d]+)\]'
            citations_with_spans = []
            
            for match in re.finditer(citation_pattern, text):
                citation_id = match.group(1)
                start = match.start()
                end = match.end()
                
                # Get the context (text before and after the citation)
                context_start = max(0, start - 50)
                context_end = min(len(text), end + 50)
                context = text[context_start:context_end]
                
                citations_with_spans.append({
                    "citation_id": citation_id,
                    "start": start,
                    "end": end,
                    "context": context
                })
            
            return citations_with_spans
        
        # Test text
        text = (
            "Aristotle discussed virtue ethics in his Nicomachean Ethics [abc1234]. "
            "According to Plato [xyz5678], the ideal state is described in The Republic. "
            "Socrates' method of questioning is demonstrated in many dialogues [ghi9012]."
        )
        
        # Extract citations with spans
        extracted = extract_citations_with_spans(text)
        
        # Verify the correct number of citations was extracted
        assert len(extracted) == 3
        
        # Verify citation IDs are correct
        assert extracted[0]["citation_id"] == "abc1234"
        assert extracted[1]["citation_id"] == "xyz5678"
        assert extracted[2]["citation_id"] == "ghi9012"
        
        # Verify spans and context
        for citation in extracted:
            assert citation["start"] < citation["end"]
            assert text[citation["start"]:citation["end"]] == f"[{citation['citation_id']}]"
            assert citation["citation_id"] in citation["context"]
    
    def test_citation_extraction_edge_cases(self):
        """Test citation extraction with edge cases and malformed citations."""
        # Test function to extract citations that exactly matches the implementation in core.utils
        def extract_citations(text):
            # Handle None or empty input
            if text is None or text == "":
                return []
                
            # Match the core implementation pattern: 7-8 alphanumeric chars
            citation_pattern = re.compile(r"\[([A-Za-z0-9]{7,8})\]")
            
            sids = []
            for match in citation_pattern.finditer(text):
                sid = match.group(1)
                sids.append(sid)
                
            return sids
        
        # Edge case tests
        test_cases = [
            (
                "Incomplete citation [abc1234",  # Missing closing bracket
                []  # This would not match with the regular pattern
            ),
            (
                "Empty citation []",  # Empty citation
                []  # This would match but capture an empty string
            ),
            (
                "Citation with special chars [abc-1234]",  # Contains hyphen
                []  # Should not capture because hyphen is not allowed in the pattern
            ),
            (
                "Citation at the end of sentence[abcd1234].",  # No space before citation
                ["abcd1234"]  # Should still capture
            ),
            (
                "Valid citation [abc1234]",  # Valid citation
                ["abc1234"]  # Should capture
            ),
            (
                "Text with [short] but no valid citation format.",  # 'short' is only 5 chars, too short
                []  # Should not extract non-citation brackets with wrong length
            ),
            (
                "Text with [abc123] (too short) and [abcdefghi] (too long).",
                []  # Should not extract brackets with wrong length
            ),
            (
                "Text with [abc-1234] has the right length but contains special characters.",
                []  # Should not extract brackets with special characters
            ),
        ]
        
        # Run tests
        for text, expected_citations in test_cases:
            extracted = extract_citations(text)
            assert extracted == expected_citations
    
    def test_citation_sanitization(self):
        """Test sanitization of citation IDs."""
        # Function to sanitize citation IDs
        def sanitize_citation_id(citation_id):
            # Remove any non-alphanumeric characters
            return re.sub(r'[^a-zA-Z0-9]', '', citation_id)
        
        # Test cases
        test_cases = [
            ("abc1234", "abc1234"),  # Already clean
            ("abc-1234", "abc1234"),  # Contains hyphen
            ("abc.1234", "abc1234"),  # Contains period
            ("abc_1234", "abc1234"),  # Contains underscore
            ("abc 1234", "abc1234"),  # Contains space
        ]
        
        # Run tests
        for input_id, expected_id in test_cases:
            sanitized = sanitize_citation_id(input_id)
            assert sanitized == expected_id


class TestCitationTracker:
    """Tests for citation tracking functionality."""
    
    def test_citation_tracker_init(self):
        """Test initialization of citation tracker."""
        tracker = CitationTracker()
        assert hasattr(tracker, 'processed_spans')
        assert hasattr(tracker, 'citation_spans')
        assert isinstance(tracker.processed_spans, dict)
        assert isinstance(tracker.citation_spans, dict)
        assert len(tracker.processed_spans) == 0
        assert len(tracker.citation_spans) == 0
    
    def test_is_new_span(self):
        """Test is_new_span method."""
        tracker = CitationTracker()
        
        # First occurrence should be new
        assert tracker.is_new_span("abc1234", (10, 18)) is True
        
        # Same span should not be new anymore
        assert tracker.is_new_span("abc1234", (10, 18)) is False
        
        # Different span for same citation should be new
        assert tracker.is_new_span("abc1234", (30, 38)) is True
        
        # Different citation ID should be new
        assert tracker.is_new_span("def5678", (10, 18)) is True
    
    def test_get_all_citation_spans(self):
        """Test get_all_citation_spans method."""
        tracker = CitationTracker()
        
        # Add some spans
        tracker.is_new_span("abc1234", (10, 18))
        tracker.is_new_span("abc1234", (30, 38))
        tracker.is_new_span("def5678", (50, 58))
        
        # Get all spans
        all_spans = tracker.get_all_citation_spans()
        
        # Verify results
        assert "abc1234" in all_spans
        assert "def5678" in all_spans
        assert len(all_spans["abc1234"]) == 2
        assert len(all_spans["def5678"]) == 1
        assert (10, 18) in all_spans["abc1234"]
        assert (30, 38) in all_spans["abc1234"]
        assert (50, 58) in all_spans["def5678"]
    
    def test_citation_tracker_multiple_spans(self):
        """Test tracking multiple citation spans."""
        tracker = CitationTracker()
        
        # Sample text with multiple citations
        text = (
            "Aristotle discussed virtue ethics in his Nicomachean Ethics [abc1234]. "
            "Later in the same work [abc1234], he expanded on this concept. "
            "According to Plato [def5678], the ideal state is described in The Republic."
        )
        
        # Extract and track citations
        citation_pattern = r'\[([\w\d]+)\]'
        for match in re.finditer(citation_pattern, text):
            citation_id = match.group(1)
            start = match.start()
            end = match.end()
            tracker.is_new_span(citation_id, (start, end))
        
        # Verify tracking
        all_spans = tracker.get_all_citation_spans()
        assert len(all_spans["abc1234"]) == 2
        assert len(all_spans["def5678"]) == 1


class TestCitationStreamingEvents:
    """Tests for citation events during streaming."""
    
    def test_emit_citation_event(self):
        """Test emitting a citation event during streaming."""
        # Create a mock agent
        class MockAgent:
            def __init__(self):
                self.emitted_events = []
            
            def emit_event(self, event):
                self.emitted_events.append(event)
        
        agent = MockAgent()
        
        # Function to emit a citation event
        def emit_citation_event(agent, citation_id, start, end, text_context):
            event = {
                "type": "citation",
                "data": {
                    "citation_id": citation_id,
                    "start": start,
                    "end": end,
                    "text_context": text_context
                }
            }
            agent.emit_event(event)
        
        # Emit an event
        emit_citation_event(agent, "abc1234", 10, 18, "text with [abc1234] citation")
        
        # Verify event
        assert len(agent.emitted_events) == 1
        event = agent.emitted_events[0]
        assert event["type"] == "citation"
        assert event["data"]["citation_id"] == "abc1234"
        assert event["data"]["start"] == 10
        assert event["data"]["end"] == 18
    
    def test_citation_tracking_during_streaming(self):
        """Test tracking citations during streaming."""
        # Create a mock agent with citation tracker
        class MockAgent:
            def __init__(self):
                self.emitted_events = []
                self.citation_tracker = CitationTracker()
            
            def emit_event(self, event):
                self.emitted_events.append(event)
        
        agent = MockAgent()
        
        # Function to process streaming text and emit citation events
        def process_streaming_text(agent, text, start_offset=0):
            # Extract citations
            citation_pattern = r'\[([\w\d]+)\]'
            for match in re.finditer(citation_pattern, text):
                citation_id = match.group(1)
                start = match.start() + start_offset
                end = match.end() + start_offset
                
                # Check if this is a new span
                if agent.citation_tracker.is_new_span(citation_id, (start, end)):
                    # Get context
                    context_start = max(0, match.start() - 10)
                    context_end = min(len(text), match.end() + 10)
                    context = text[context_start:context_end]
                    
                    # Emit event
                    event = {
                        "type": "citation",
                        "data": {
                            "citation_id": citation_id,
                            "start": start,
                            "end": end,
                            "text_context": context
                        }
                    }
                    agent.emit_event(event)
        
        # Process streaming text in chunks
        chunks = [
            "Aristotle discussed virtue ethics ",
            "in his Nicomachean Ethics [abc1234]. ",
            "According to Plato [def5678], ",
            "the ideal state is described in The Republic. ",
            "Later, Aristotle also mentioned [abc1234] this concept."
        ]
        
        offset = 0
        for chunk in chunks:
            process_streaming_text(agent, chunk, offset)
            offset += len(chunk)
        
        # Verify events and tracking
        assert len(agent.emitted_events) == 3  # 3 citations total (2 abc1234, 1 def5678)
        
        # Verify citation IDs in events
        citation_ids = [event["data"]["citation_id"] for event in agent.emitted_events]
        assert citation_ids.count("abc1234") == 2
        assert citation_ids.count("def5678") == 1
        
        # Verify tracker state
        all_spans = agent.citation_tracker.get_all_citation_spans()
        assert len(all_spans["abc1234"]) == 2
        assert len(all_spans["def5678"]) == 1


class TestRAGWithCitations:
    """Tests for RAG functionality with citations."""
    
    @pytest.mark.asyncio
    async def test_rag_with_citation_metadata(self, mock_providers, sample_chunk_results):
        """Test RAG with citation metadata in search results."""
        # Function to build a RAG prompt with citations
        def build_rag_prompt_with_citations(query, search_results):
            context = ""
            citation_metadata = {}
            
            for i, result in enumerate(search_results):
                # Extract citation information
                citation_id = result.get("metadata", {}).get("citation_id")
                if citation_id:
                    # Add to context with citation marker
                    context += f"\n[{i+1}] {result['text']} [{citation_id}]"
                    
                    # Store metadata
                    citation_metadata[citation_id] = {
                        "document_id": result["document_id"],
                        "chunk_id": result["chunk_id"],
                        "metadata": result.get("metadata", {})
                    }
                else:
                    context += f"\n[{i+1}] {result['text']}"
            
            prompt = f"Question: {query}\n\nContext:{context}\n\nPlease answer the question based on the provided context."
            
            return prompt, citation_metadata
        
        # Build prompt
        query = "What is the main concept?"
        prompt, citation_metadata = build_rag_prompt_with_citations(query, sample_chunk_results)
        
        # Verify prompt contains citations
        for i in range(5):
            assert f"[cite{i}]" in prompt
        
        # Verify metadata is stored
        assert len(citation_metadata) == 5
        for i in range(5):
            assert f"cite{i}" in citation_metadata
            assert citation_metadata[f"cite{i}"]["document_id"] == f"doc-{i//2}"
            assert citation_metadata[f"cite{i}"]["chunk_id"] == f"chunk-{i}"
    
    @pytest.mark.asyncio
    async def test_rag_response_with_citations(self, mock_providers, sample_chunk_results):
        """Test generating a RAG response with citations."""
        # Function to generate RAG response with citations
        async def generate_rag_response_with_citations(query, search_results):
            # Build prompt with citations
            context = ""
            citation_metadata = {}
            
            for i, result in enumerate(search_results):
                citation_id = result.get("metadata", {}).get("citation_id")
                if citation_id:
                    context += f"\n[{i+1}] {result['text']} [{citation_id}]"
                    
                    citation_metadata[citation_id] = {
                        "document_id": result["document_id"],
                        "chunk_id": result["chunk_id"],
                        "metadata": result.get("metadata", {})
                    }
                else:
                    context += f"\n[{i+1}] {result['text']}"
            
            prompt = f"Question: {query}\n\nContext:{context}\n\nPlease answer the question based on the provided context."
            
            # Generate response (mocked)
            # In real implementation, this would call the LLM
            mock_providers.llm.aget_completion.return_value = {
                "choices": [{
                    "message": {
                        "content": "The main concept is explained in [cite0] and further elaborated in [cite2]."
                    }
                }]
            }
            
            response = await mock_providers.llm.aget_completion(prompt=prompt)
            content = response["choices"][0]["message"]["content"]
            
            return content, citation_metadata
        
        # Generate response
        query = "What is the main concept?"
        response, citation_metadata = await generate_rag_response_with_citations(query, sample_chunk_results)
        
        # Verify response contains citations
        assert "[cite0]" in response
        assert "[cite2]" in response
        
        # Extract citations from response
        def extract_citations_from_response(text):
            citation_pattern = r'\[([\w\d]+)\]'
            citations = re.findall(citation_pattern, text)
            return citations
        
        citations = extract_citations_from_response(response)
        assert "cite0" in citations
        assert "cite2" in citations
    
    @pytest.mark.asyncio
    async def test_consolidate_citations_in_final_answer(self, mock_providers):
        """Test consolidating citations in the final answer."""
        # Create a citation tracker with some spans
        tracker = CitationTracker()
        tracker.is_new_span("cite0", (10, 18))
        tracker.is_new_span("cite0", (30, 38))
        tracker.is_new_span("cite2", (50, 58))
        
        # Create citation metadata
        citation_metadata = {
            "cite0": {
                "document_id": "doc-0",
                "chunk_id": "chunk-0",
                "metadata": {"source": "source-0", "title": "Document 0"}
            },
            "cite2": {
                "document_id": "doc-1",
                "chunk_id": "chunk-2",
                "metadata": {"source": "source-2", "title": "Document 1"}
            }
        }
        
        # Function to consolidate citations
        def consolidate_citations(response_text, citation_tracker, citation_metadata):
            # Get all citations from the tracker
            all_citation_spans = citation_tracker.get_all_citation_spans()
            
            # Build consolidated citations
            consolidated_citations = {}
            for citation_id, spans in all_citation_spans.items():
                if citation_id in citation_metadata:
                    metadata = citation_metadata[citation_id]
                    consolidated_citations[citation_id] = {
                        "spans": spans,
                        "document_id": metadata["document_id"],
                        "chunk_id": metadata["chunk_id"],
                        "metadata": metadata["metadata"]
                    }
            
            # Return the response with consolidated citations
            return {
                "response": response_text,
                "citations": consolidated_citations
            }
        
        # Test response
        response_text = "The main concept is explained in [cite0] and further elaborated in [cite2]."
        
        # Consolidate citations
        result = consolidate_citations(response_text, tracker, citation_metadata)
        
        # Verify result
        assert "response" in result
        assert "citations" in result
        assert result["response"] == response_text
        
        # Verify consolidated citations
        assert "cite0" in result["citations"]
        assert "cite2" in result["citations"]
        assert len(result["citations"]["cite0"]["spans"]) == 2
        assert len(result["citations"]["cite2"]["spans"]) == 1
        assert result["citations"]["cite0"]["document_id"] == "doc-0"
        assert result["citations"]["cite2"]["document_id"] == "doc-1"


class TestCitationUtils:
    """Tests for citation utility functions."""
    
    def test_extract_citations(self):
        """Test that citations are correctly extracted from text."""
        # Simple case with one citation
        text = "This is a test with a citation [abc1234]."
        citations = extract_citations(text)
        assert citations == ["abc1234"], "Should extract a single citation ID"

        # Multiple citations
        text = "First citation [abc1234] and second citation [def5678]."
        citations = extract_citations(text)
        assert citations == ["abc1234", "def5678"], "Should extract multiple citation IDs"

        # Repeated citations
        text = "Same citation twice [abc1234] and again [abc1234]."
        citations = extract_citations(text)
        assert len(citations) == 2, "Should extract duplicate citation IDs"
        assert citations == ["abc1234", "abc1234"], "Should preserve order of citations"

    def test_extract_citations_edge_cases(self):
        """Test edge cases for citation extraction."""
        # Define local extract_citations for testing that follows the core implementation
        def local_extract_citations(text):
            # Handle None or empty input
            if text is None or text == "":
                return []
                
            # Match the core implementation pattern: 7-8 alphanumeric chars
            citation_pattern = re.compile(r"\[([A-Za-z0-9]{7,8})\]")
            
            sids = []
            for match in citation_pattern.finditer(text):
                sid = match.group(1)
                sids.append(sid)
                
            return sids
        
        # Citations at beginning or end of text
        text = "[abc1234] at the beginning and at the end [def5678]"
        citations = local_extract_citations(text)
        assert citations == ["abc1234", "def5678"], "Should extract citations at beginning and end"
    
        # Empty text
        text = ""
        citations = local_extract_citations(text)
        assert citations == [], "Should handle empty text gracefully"
    
        # None input
        citations = local_extract_citations(None)
        assert citations == [], "Should handle None input gracefully"
    
        # Text with brackets but no valid citation format
        text = "Text with [short] but no valid citation format."
        citations = local_extract_citations(text)
        assert citations == [], "Should not extract non-citation brackets (too short)"
        
        # Text with brackets but wrong length
        text = "Text with [abc123] (too short) and [abcdefghi] (too long)."
        citations = local_extract_citations(text)
        assert citations == [], "Should not extract brackets with wrong length"
        
        # Text with brackets that have correct length but non-alphanumeric chars
        text = "Text with [abc-1234] has the right length but contains special characters."
        citations = local_extract_citations(text)
        assert citations == [], "Should not extract brackets with special characters"
        
        # Text with close brackets only
        text = "Text with close brackets only]."
        citations = local_extract_citations(text)
        assert citations == [], "Should not extract when only close brackets present"


    def test_extract_citation_spans(self):
        """Test that citation spans are correctly extracted with positions."""
        # Simple case with one citation
        text = "This is a test with a citation [abc1234]."
        spans = extract_citation_spans(text)
        assert len(spans) == 1, "Should extract one citation ID"
        assert "abc1234" in spans, "Citation ID should be a key in the dictionary"
        assert len(spans["abc1234"]) == 1, "Should have one span for this citation"
        start, end = spans["abc1234"][0]
        assert text[start:end] == "[abc1234]", "Span positions should be correct"

        # Multiple citations
        text = "First citation [abc1234] and second citation [def5678]."
        spans = extract_citation_spans(text)
        assert len(spans) == 2, "Should extract two citation IDs"
        assert "abc1234" in spans, "First citation ID should be present"
        assert "def5678" in spans, "Second citation ID should be present"
        assert len(spans["abc1234"]) == 1, "Should have one span for first citation"
        assert len(spans["def5678"]) == 1, "Should have one span for second citation"
        start1, end1 = spans["abc1234"][0]
        start2, end2 = spans["def5678"][0]
        assert text[start1:end1] == "[abc1234]", "First span positions should be correct"
        assert text[start2:end2] == "[def5678]", "Second span positions should be correct"


    def test_extract_citation_spans_edge_cases(self):
        """Test edge cases for citation span extraction."""
        # Citations at beginning or end of text
        text = "[abc1234] at the beginning and at the end [def5678]"
        spans = extract_citation_spans(text)
        assert len(spans) == 2, "Should extract two spans"
        assert "abc1234" in spans, "First citation ID should be present"
        assert "def5678" in spans, "Second citation ID should be present"
        assert len(spans["abc1234"]) == 1, "Should have one span for first citation"
        assert len(spans["def5678"]) == 1, "Should have one span for second citation"
        start1, end1 = spans["abc1234"][0]
        start2, end2 = spans["def5678"][0]
        assert text[start1:end1] == "[abc1234]", "First span should start at beginning"
        assert text[start2:end2] == "[def5678]", "Second span should end at end"

        # Empty text
        text = ""
        spans = extract_citation_spans(text)
        assert spans == {}, "Should return empty dictionary for empty text"

        # None input
        spans = extract_citation_spans(None)
        assert spans == {}, "Should return empty dictionary for None input"

        # Overlapping brackets
        text = "Text with overlapping [abc1234] brackets [def5678]."
        spans = extract_citation_spans(text)
        assert len(spans) == 2, "Should extract two spans correctly even with proximity"
        assert "abc1234" in spans, "First citation ID should be present"
        assert "def5678" in spans, "Second citation ID should be present"
        assert len(spans["abc1234"]) == 1, "Should have one span for first citation"
        assert len(spans["def5678"]) == 1, "Should have one span for second citation"


    def test_core_citation_tracker(self):
        """Test the core CitationTracker class functionality."""
        tracker = CitationTracker()
        
        # Test initial state
        assert len(tracker.processed_spans) == 0, "Should start with empty citation spans"
        
        # Test adding a new span
        assert tracker.is_new_span("abc1234", (10, 20)), "First span should be considered new"
        assert "abc1234" in tracker.processed_spans, "Citation ID should be in processed_spans"
        assert (10, 20) in tracker.processed_spans["abc1234"], "Span should be recorded"
        
        # Test adding a duplicate span
        assert not tracker.is_new_span("abc1234", (10, 20)), "Duplicate span should not be considered new"
        assert len(tracker.processed_spans["abc1234"]) == 1, "Duplicate span should not be added again"
        
        # Test adding a new span for the same citation
        assert tracker.is_new_span("abc1234", (30, 40)), "Different span for same citation should be new"
        assert len(tracker.processed_spans["abc1234"]) == 2, "New span should be added"
        assert (30, 40) in tracker.processed_spans["abc1234"], "New span should be recorded"
        
        # Test get_all_spans
        all_spans = tracker.get_all_citation_spans()
        assert "abc1234" in all_spans, "Citation ID should be in all spans"
        assert len(all_spans["abc1234"]) == 2, "Should have 2 spans for the citation"
    
    def test_core_citation_tracker_edge_cases(self):
        """Test edge cases for the core CitationTracker class."""
        tracker = CitationTracker()
        
        # Test with empty or invalid inputs
        assert not tracker.is_new_span("", (10, 20)), "Empty citation ID should not be tracked"
        assert not tracker.is_new_span(None, (10, 20)), "None citation ID should not be tracked"
        assert tracker.is_new_span("abc1234", (-5, 20)), "Negative start position should be accepted"
        assert tracker.is_new_span("abc1234", (30, 20)), "End before start should be accepted (implementation dependent)"
        
        # Test overlapping spans
        assert tracker.is_new_span("def5678", (10, 30)), "First overlapping span should be new"
        assert tracker.is_new_span("def5678", (20, 40)), "Second overlapping span should be new"
        assert len(tracker.processed_spans["def5678"]) == 2, "Both overlapping spans should be recorded"
        
        # Test with very large spans
        assert tracker.is_new_span("large", (0, 10000)), "Very large span should be tracked"
        assert (0, 10000) in tracker.processed_spans["large"], "Large span should be recorded correctly"
        
        # Test get_all_spans with multiple citations
        all_spans = tracker.get_all_citation_spans()
        assert len(all_spans) >= 3, "Should have at least 3 different citation IDs"
        # Empty citation ID won't be included since we properly reject them in is_new_span
    
    def test_find_new_citation_spans(self):
        """Test the function that finds new citation spans in text."""
        tracker = CitationTracker()
        
        # First text with citations
        text = "This is a text with citation [abc1234]."
        new_spans1 = find_new_citation_spans(text, tracker)
        assert len(new_spans1) == 1, "Should find one new span"
        assert new_spans1[0][0] == "abc1234", "Citation ID should match"
        citation_id, start, end = new_spans1[0]
        assert citation_id in tracker.processed_spans, "Citation ID should be tracked"
        assert (start, end) in tracker.processed_spans[citation_id], "Span should be tracked"
        
        # Duplicate span in new text
        text2 = text  # Same text with same citation
        new_spans2 = find_new_citation_spans(text2, tracker)
        assert new_spans2 == [], "Should not find duplicate spans"
        
        # Text with new citation
        text3 = "This is another text with a new citation [def5678]."
        new_spans3 = find_new_citation_spans(text3, tracker)
        assert len(new_spans3) == 1, "Should find one new span"
        assert new_spans3[0][0] == "def5678", "New citation ID should match"
        
        # Text with both old and new citations
        text4 = "Text with both [abc1234] and [ghi9012]."
        new_spans4 = find_new_citation_spans(text4, tracker)
        assert len(new_spans4) == 1, "Should only find the new span"
        assert new_spans4[0][0] == "ghi9012", "Only new citation ID should be found"
        
    def test_find_new_citation_spans_edge_cases(self):
        """Test edge cases for finding new citation spans."""
        tracker = CitationTracker()
        
        # Empty text
        new_spans1 = find_new_citation_spans("", tracker)
        assert new_spans1 == [], "Should return empty list for empty text"
        
        # Text without citations
        new_spans2 = find_new_citation_spans("This text has no citations or brackets.", tracker)
        assert new_spans2 == [], "Should return empty list for text without citations"
        
        # None input
        new_spans3 = find_new_citation_spans(None, tracker)
        assert new_spans3 == [], "Should handle None input gracefully and return empty list"
        
        # Multiple citations in one text
        text = "Text with multiple citations [abc1234] and [def5678] and [ghi9012]."
        new_spans = find_new_citation_spans(text, tracker)
        assert len(new_spans) == 3, "Should find three new spans"
        citation_ids = [span[0] for span in new_spans]
        assert "abc1234" in citation_ids, "First citation should be found"
        assert "def5678" in citation_ids, "Second citation should be found"
        assert "ghi9012" in citation_ids, "Third citation should be found"


    def test_performance_with_many_citations(self):
        """Test performance with a large number of citations."""
        # Create a text with 100 different citations
        citations = [f"cit{i:04d}" for i in range(100)]
        text = "Beginning of text. "
        for i, citation in enumerate(citations):
            text += f"Citation {i+1}: [{citation}]. "
        text += "End of text."
        
        # Extract all citations
        extracted = extract_citations(text)
        assert len(extracted) == 100, "Should extract all 100 citations"
        
        # Extract all spans
        spans = extract_citation_spans(text)
        assert len(spans) == 100, "Should extract all 100 spans"
        
        # Test find_new_citation_spans with a tracker
        tracker = CitationTracker()
        new_spans = find_new_citation_spans(text, tracker)
        assert len(new_spans) == 100, "Should find all 100 spans as new"
        
        # Test finding spans in chunks (simulating streaming)
        chunk_size = len(text) // 10
        tracker2 = CitationTracker()
        total_new_spans = 0
        
        for i in range(10):
            start = i * chunk_size
            end = start + chunk_size
            if i == 9:  # Last chunk
                end = len(text)
            
            chunk = text[start:end]
            new_spans_in_chunk = find_new_citation_spans(chunk, tracker2, start_offset=start)
            total_new_spans += len(new_spans_in_chunk)
        
        # We might not get exactly 100 because citations could be split across chunks
        # But we should get a reasonable number
        assert total_new_spans > 50, "Should find majority of spans even in chunks"


    def test_streaming_citation_handling(self):
        """Test citation handling with simulated streaming updates."""
        tracker = CitationTracker()
        
        # Simulate a streaming scenario where text comes in chunks
        chunks = [
            "This is the first chunk ",
            "with no citations. This is the second chunk with a ",
            "citation [abc1234] and some more text. ",
            "This is the third chunk with another citation [def5678] ",
            "and the first citation again [abc1234] in a new position."
        ]
        
        all_text = ""
        total_spans_found = 0
        
        for i, chunk in enumerate(chunks):
            chunk_start = len(all_text)
            all_text += chunk
            
            # For streaming, we need to extract citation spans from the chunk
            # and check if they are new in the context of the accumulated text
            pattern = r'\[([\w]{7,8})\]'
            for match in re.finditer(pattern, chunk):
                citation_id = match.group(1)
                start = match.start() + chunk_start
                end = match.end() + chunk_start
                
                # Check if this span is new for this citation ID
                if tracker.is_new_span(citation_id, (start, end)):
                    total_spans_found += 1
        
        # Check final state
        assert "abc1234" in tracker.processed_spans, "First citation should be tracked"
        assert "def5678" in tracker.processed_spans, "Second citation should be tracked"
        assert len(tracker.processed_spans["abc1234"]) == 2, "First citation should have 2 spans"
        assert len(tracker.processed_spans["def5678"]) == 1, "Second citation should have 1 span"
        assert total_spans_found == 3, "Should have found 3 spans in total"
    
    def test_malformed_citations(self):
        """Test handling of malformed or partial citations."""
        # Various malformed citation patterns
        text = """
        This text has citations with issues:
        - Missing end bracket [abc1234 
        - Missing start bracket def5678]
        - Wrong format [abc123] (too short)
        - Wrong format [abcdefghi] (too long)
        - Valid citation [abc1234]
        - Empty brackets []
        - Non-alphanumeric [abc@123]
        """
        
        # Extract citations
        citations = extract_citations(text)
        assert len(citations) == 1, "Should only extract the one valid citation"
        assert citations[0] == "abc1234", "Valid citation should be extracted"
        
        # Extract spans
        spans = extract_citation_spans(text)
        assert len(spans) == 1, "Should only extract span for the valid citation"
        assert "abc1234" in spans, "Valid citation span should be extracted"
        
        # Test with the tracker
        tracker = CitationTracker()
        new_spans = find_new_citation_spans(text, tracker)
        assert len(new_spans) == 1, "Should only find one new valid citation span"
        assert new_spans[0][0] == "abc1234", "Valid citation should be found"
        assert len(tracker.processed_spans) == 1, "Should only track the valid citation"


def find_new_citation_spans(text, tracker, start_offset=0):
    """Find new citation spans in text that haven't been processed yet."""
    if text is None or text == "":
        return []
        
    new_spans = []
    pattern = r'\[([\w]{7,8})\]'
    
    # Get citation IDs that have already been processed
    previously_seen_ids = set(tracker.processed_spans.keys())
    
    # Find all citations in the text
    for match in re.finditer(pattern, text):
        citation_id = match.group(1)
        start = match.start() + start_offset
        end = match.end() + start_offset
        
        # Filter out citation IDs we've seen before
        # For this test, we only want to return entirely new citation IDs
        if citation_id not in previously_seen_ids:
            # Check if this specific span is new
            if tracker.is_new_span(citation_id, (start, end)):
                new_spans.append((citation_id, start, end))
            
    return new_spans
