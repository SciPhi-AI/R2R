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
        self.processed_spans = set()
        self.citation_spans = {}
    
    def is_new_span(self, citation_id, start, end):
        """Check if this span is new and mark it as processed if it is."""
        span = (citation_id, start, end)
        if span in self.processed_spans:
            return False
        
        self.processed_spans.add(span)
        
        # Also track by citation ID for easy lookup
        if citation_id not in self.citation_spans:
            self.citation_spans[citation_id] = []
        
        self.citation_spans[citation_id].append((start, end))
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
                return_value={"choices": [{"message": {"content": "Response with [abc123] citation"}}]}
            )
            self.llm.aget_completion_stream = AsyncMock(
                return_value=iter([
                    {"choices": [{"delta": {"content": "Response "}}]},
                    {"choices": [{"delta": {"content": "with "}}]},
                    {"choices": [{"delta": {"content": "[abc123] "}}]},
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
                "Aristotle discussed virtue ethics in his Nicomachean Ethics [abc123].",
                ["abc123"]
            ),
            (
                "According to Plato [xyz456] and Aristotle [abc123], philosophy is important.",
                ["xyz456", "abc123"]
            ),
            (
                "This text has no citations.",
                []
            ),
            (
                "Multiple citations in a row [abc123][def456][ghi789] should all be found.",
                ["abc123", "def456", "ghi789"]
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
            "Aristotle discussed virtue ethics in his Nicomachean Ethics [abc123]. "
            "According to Plato [xyz456], the ideal state is described in The Republic. "
            "Socrates' method of questioning is demonstrated in many dialogues [ghi789]."
        )
        
        # Extract citations with spans
        extracted = extract_citations_with_spans(text)
        
        # Verify the correct number of citations was extracted
        assert len(extracted) == 3
        
        # Verify citation IDs are correct
        assert extracted[0]["citation_id"] == "abc123"
        assert extracted[1]["citation_id"] == "xyz456"
        assert extracted[2]["citation_id"] == "ghi789"
        
        # Verify spans and context
        for citation in extracted:
            assert citation["start"] < citation["end"]
            assert text[citation["start"]:citation["end"]] == f"[{citation['citation_id']}]"
            assert citation["citation_id"] in citation["context"]
    
    def test_citation_extraction_edge_cases(self):
        """Test citation extraction with edge cases and malformed citations."""
        # Test function to extract citations
        def extract_citations(text):
            citation_pattern = r'\[([\w\d]+)\]'
            citations = re.findall(citation_pattern, text)
            return citations
        
        # Edge case tests
        test_cases = [
            (
                "Incomplete citation [abc123",  # Missing closing bracket
                []  # This would not match with the regular pattern
            ),
            (
                "Empty citation []",  # Empty citation
                []  # This would match but capture an empty string
            ),
            (
                "Citation with special chars [abc-123]",  # Contains hyphen
                ["abc-123"]  # Should capture if the pattern allows -
            ),
            (
                "Citation at the end of sentence[abc123].",  # No space before citation
                ["abc123"]  # Should still capture
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
            ("abc123", "abc123"),  # Already clean
            ("abc-123", "abc123"),  # Contains hyphen
            ("abc.123", "abc123"),  # Contains period
            ("abc_123", "abc123"),  # Contains underscore
            ("abc 123", "abc123"),  # Contains space
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
        assert isinstance(tracker.processed_spans, set)
        assert isinstance(tracker.citation_spans, dict)
        assert len(tracker.processed_spans) == 0
        assert len(tracker.citation_spans) == 0
    
    def test_is_new_span(self):
        """Test is_new_span method."""
        tracker = CitationTracker()
        
        # First occurrence should be new
        assert tracker.is_new_span("abc123", 10, 18) is True
        
        # Same span should not be new anymore
        assert tracker.is_new_span("abc123", 10, 18) is False
        
        # Different span for same citation should be new
        assert tracker.is_new_span("abc123", 30, 38) is True
        
        # Different citation ID should be new
        assert tracker.is_new_span("def456", 10, 18) is True
    
    def test_get_all_citation_spans(self):
        """Test get_all_citation_spans method."""
        tracker = CitationTracker()
        
        # Add some spans
        tracker.is_new_span("abc123", 10, 18)
        tracker.is_new_span("abc123", 30, 38)
        tracker.is_new_span("def456", 50, 58)
        
        # Get all spans
        all_spans = tracker.get_all_citation_spans()
        
        # Verify results
        assert "abc123" in all_spans
        assert "def456" in all_spans
        assert len(all_spans["abc123"]) == 2
        assert len(all_spans["def456"]) == 1
        assert (10, 18) in all_spans["abc123"]
        assert (30, 38) in all_spans["abc123"]
        assert (50, 58) in all_spans["def456"]
    
    def test_citation_tracker_multiple_spans(self):
        """Test tracking multiple citation spans."""
        tracker = CitationTracker()
        
        # Sample text with multiple citations
        text = (
            "Aristotle discussed virtue ethics in his Nicomachean Ethics [abc123]. "
            "Later in the same work [abc123], he expanded on this concept. "
            "According to Plato [def456], the ideal state is described in The Republic."
        )
        
        # Extract and track citations
        citation_pattern = r'\[([\w\d]+)\]'
        for match in re.finditer(citation_pattern, text):
            citation_id = match.group(1)
            start = match.start()
            end = match.end()
            tracker.is_new_span(citation_id, start, end)
        
        # Verify tracking
        all_spans = tracker.get_all_citation_spans()
        assert len(all_spans["abc123"]) == 2
        assert len(all_spans["def456"]) == 1


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
        emit_citation_event(agent, "abc123", 10, 18, "text with [abc123] citation")
        
        # Verify event
        assert len(agent.emitted_events) == 1
        event = agent.emitted_events[0]
        assert event["type"] == "citation"
        assert event["data"]["citation_id"] == "abc123"
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
                if agent.citation_tracker.is_new_span(citation_id, start, end):
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
            "in his Nicomachean Ethics [abc123]. ",
            "According to Plato [def456], ",
            "the ideal state is described in The Republic. ",
            "Later, Aristotle also mentioned [abc123] this concept."
        ]
        
        offset = 0
        for chunk in chunks:
            process_streaming_text(agent, chunk, offset)
            offset += len(chunk)
        
        # Verify events and tracking
        assert len(agent.emitted_events) == 3  # 3 citations total (2 abc123, 1 def456)
        
        # Verify citation IDs in events
        citation_ids = [event["data"]["citation_id"] for event in agent.emitted_events]
        assert citation_ids.count("abc123") == 2
        assert citation_ids.count("def456") == 1
        
        # Verify tracker state
        all_spans = agent.citation_tracker.get_all_citation_spans()
        assert len(all_spans["abc123"]) == 2
        assert len(all_spans["def456"]) == 1


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
        tracker.is_new_span("cite0", 10, 18)
        tracker.is_new_span("cite0", 30, 38)
        tracker.is_new_span("cite2", 50, 58)
        
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
        assert citations == ["abc1234", "abc1234"], "Should extract repeated citations separately"

        # No citations
        text = "Text with no citations."
        citations = extract_citations(text)
        assert citations == [], "Should return empty list when no citations"

        # Invalid format (not matching pattern)
        text = "Invalid citation format [abc123] or [abcd12345]."
        citations = extract_citations(text)
        assert citations == [], "Should not extract citations with invalid format"


    def test_extract_citations_edge_cases(self):
        """Test edge cases for citation extraction."""
        # Citations at beginning or end of text
        text = "[abc1234] at the beginning and at the end [def5678]"
        citations = extract_citations(text)
        assert citations == ["abc1234", "def5678"], "Should extract citations at beginning and end"

        # Empty text
        text = ""
        citations = extract_citations(text)
        assert citations == [], "Should handle empty text gracefully"

        # None input (current implementation raises TypeError, which is expected)
        try:
            extract_citations(None)
            pytest.fail("Should have raised TypeError for None input")
        except TypeError:
            pass  # Expected behavior

        # Text with brackets but no valid citation format
        text = "Text with [brackets] but no valid citation format."
        citations = extract_citations(text)
        assert citations == [], "Should not extract non-citation brackets"

        # Text with close brackets only
        text = "Text with close brackets only]."
        citations = extract_citations(text)
        assert citations == [], "Should not extract when only close brackets present"


    def test_extract_citation_spans(self):
        """Test that citation spans are correctly extracted with positions."""
        # Simple case with one citation
        text = "This is a test with a citation [abc1234]."
        spans = extract_citation_spans(text)
        assert len(spans) == 1, "Should extract one span"
        assert spans[0][0] == "abc1234", "Citation ID should match"
        assert text[spans[0][1]:spans[0][2]].strip() == "[abc1234]", "Span positions should be correct"

        # Multiple citations
        text = "First citation [abc1234] and second citation [def5678]."
        spans = extract_citation_spans(text)
        assert len(spans) == 2, "Should extract two spans"
        assert spans[0][0] == "abc1234", "First citation ID should match"
        assert spans[1][0] == "def5678", "Second citation ID should match"
        assert text[spans[0][1]:spans[0][2]].strip() == "[abc1234]", "First span positions should be correct"
        assert text[spans[1][1]:spans[1][2]].strip() == "[def5678]", "Second span positions should be correct"


    def test_extract_citation_spans_edge_cases(self):
        """Test edge cases for citation span extraction."""
        # Citations at beginning or end of text
        text = "[abc1234] at the beginning and at the end [def5678]"
        spans = extract_citation_spans(text)
        assert len(spans) == 2, "Should extract two spans"
        assert spans[0][0] == "abc1234", "First citation ID should match"
        assert spans[1][0] == "def5678", "Second citation ID should match"
        assert text[spans[0][1]:spans[0][2]].strip() == "[abc1234]", "First span should start at beginning"
        assert text[spans[1][1]:spans[1][2]].strip() == "[def5678]", "Second span should end at end"

        # Empty text
        text = ""
        spans = extract_citation_spans(text)
        assert spans == [], "Should return empty list for empty text"

        # None input
        try:
            extract_citation_spans(None)
            pytest.fail("Should have raised TypeError for None input")
        except TypeError:
            pass  # Expected behavior

        # Overlapping brackets
        text = "Text with overlapping [abc1234] brackets [def5678]."
        spans = extract_citation_spans(text)
        assert len(spans) == 2, "Should extract two spans correctly even with proximity"
        assert spans[0][0] == "abc1234", "First citation ID should match"
        assert spans[1][0] == "def5678", "Second citation ID should match"


    def test_core_citation_tracker(self):
        """Test the core CitationTracker class functionality."""
        tracker = CoreCitationTracker()
        
        # Test initial state
        assert not tracker.citation_spans, "Should start with empty citation spans"
        
        # Test adding a new span
        assert tracker.is_new_span("abc1234", 10, 20), "First span should be considered new"
        assert tracker.citation_spans["abc1234"] == [(10, 20)], "Span should be recorded"
        
        # Test adding a duplicate span
        assert not tracker.is_new_span("abc1234", 10, 20), "Duplicate span should not be considered new"
        assert tracker.citation_spans["abc1234"] == [(10, 20)], "Duplicate span should not be added again"
        
        # Test adding a new span for the same citation
        assert tracker.is_new_span("abc1234", 30, 40), "Different span for same citation should be new"
        assert tracker.citation_spans["abc1234"] == [(10, 20), (30, 40)], "New span should be added"
        
        # Test get_all_citation_spans
        all_spans = tracker.get_all_citation_spans()
        assert "abc1234" in all_spans, "Citation ID should be in all spans"
        assert len(all_spans["abc1234"]) == 2, "Should have 2 spans for the citation"


    def test_core_citation_tracker_edge_cases(self):
        """Test edge cases for the core CitationTracker class."""
        tracker = CoreCitationTracker()
        
        # Test with empty or invalid inputs
        assert tracker.is_new_span("", 10, 20), "Empty citation ID should still be tracked"
        assert tracker.is_new_span("abc1234", -5, 20), "Negative start position should be accepted"
        assert tracker.is_new_span("abc1234", 30, 20), "End before start should be accepted (implementation dependent)"
        
        # Test overlapping spans
        assert tracker.is_new_span("def5678", 10, 30), "First overlapping span should be new"
        assert tracker.is_new_span("def5678", 20, 40), "Second overlapping span should be new"
        assert len(tracker.citation_spans["def5678"]) == 2, "Both overlapping spans should be recorded"
        
        # Test with very large spans
        assert tracker.is_new_span("large", 0, 10000), "Very large span should be tracked"
        assert tracker.citation_spans["large"] == [(0, 10000)], "Large span should be recorded correctly"
        
        # Test get_all_citation_spans with multiple citations
        all_spans = tracker.get_all_citation_spans()
        assert len(all_spans) >= 4, "Should have at least 4 different citation IDs"
        assert "" in all_spans, "Empty citation ID should be included"


    def test_find_new_citation_spans(self):
        """Test the function that finds new citation spans in text."""
        tracker = CoreCitationTracker()
        
        # First text with citations
        text1 = "This is a text with citation [abc1234]."
        new_spans1 = find_new_citation_spans(text1, tracker)
        assert len(new_spans1) == 1, "Should find one new span"
        assert new_spans1[0][0] == "abc1234", "Citation ID should match"
        assert tracker.citation_spans["abc1234"] == [(new_spans1[0][1], new_spans1[0][2])], "Span should be tracked"
        
        # Same text again, should find no new spans
        new_spans2 = find_new_citation_spans(text1, tracker)
        assert len(new_spans2) == 0, "Should find no new spans in repeated text"
        
        # New text with the same citation in a different position
        text2 = "Another text with the same citation [abc1234] but in a different position."
        new_spans3 = find_new_citation_spans(text2, tracker)
        assert len(new_spans3) == 1, "Should find one new span in new position"
        assert new_spans3[0][0] == "abc1234", "Citation ID should match"
        assert len(tracker.citation_spans["abc1234"]) == 2, "Should now have two spans for the citation"
        
        # Text with a new citation
        text3 = "Text with a new citation [def5678]."
        new_spans4 = find_new_citation_spans(text3, tracker)
        assert len(new_spans4) == 1, "Should find one new span for new citation"
        assert new_spans4[0][0] == "def5678", "New citation ID should match"
        assert tracker.citation_spans["def5678"] == [(new_spans4[0][1], new_spans4[0][2])], "New citation span should be tracked"


    def test_find_new_citation_spans_edge_cases(self):
        """Test edge cases for finding new citation spans."""
        tracker = CoreCitationTracker()
        
        # Empty text
        new_spans1 = find_new_citation_spans("", tracker)
        assert new_spans1 == [], "Should return empty list for empty text"
        
        # Text with no citations
        new_spans2 = find_new_citation_spans("Text with no citations.", tracker)
        assert new_spans2 == [], "Should return empty list for text without citations"
        
        # None input
        try:
            find_new_citation_spans(None, tracker)
            pytest.fail("Should have raised TypeError for None text")
        except TypeError:
            pass  # Expected behavior
        
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
        tracker = CoreCitationTracker()
        new_spans = find_new_citation_spans(text, tracker)
        assert len(new_spans) == 100, "Should find all 100 spans as new"
        
        # Test finding spans in chunks (simulating streaming)
        chunk_size = len(text) // 10
        tracker2 = CoreCitationTracker()
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
        tracker = CoreCitationTracker()
        
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
        
        for chunk in chunks:
            chunk_start = len(all_text)
            all_text += chunk
            
            # Find new spans in this chunk
            new_spans = find_new_citation_spans(chunk, tracker, start_offset=chunk_start)
            total_spans_found += len(new_spans)
        
        # Check final state
        assert "abc1234" in tracker.citation_spans, "First citation should be tracked"
        assert "def5678" in tracker.citation_spans, "Second citation should be tracked"
        assert len(tracker.citation_spans["abc1234"]) == 2, "First citation should have 2 spans"
        assert len(tracker.citation_spans["def5678"]) == 1, "Second citation should have 1 span"
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
        assert spans[0][0] == "abc1234", "Valid citation span should be extracted"
        
        # Test with the tracker
        tracker = CoreCitationTracker()
        new_spans = find_new_citation_spans(text, tracker)
        assert len(new_spans) == 1, "Should only find one new valid citation span"
        assert new_spans[0][0] == "abc1234", "Valid citation should be found"
        assert len(tracker.citation_spans) == 1, "Should only track the valid citation"
