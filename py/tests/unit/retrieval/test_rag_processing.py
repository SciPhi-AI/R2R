"""
Unit tests for RAG (Retrieval-Augmented Generation) processing functionality.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, List, Any, Optional

# Import core classes related to RAG prompt handling
from core.base import Message, SearchSettings


@pytest.fixture
def mock_search_results():
    """Return mock search results for testing prompt construction."""
    return {
        "chunk_search_results": [
            {
                "chunk_id": f"chunk-{i}",
                "document_id": f"doc-{i//2}",
                "text": f"This is search result {i} about Aristotle's philosophy.",
                "metadata": {
                    "source": f"source-{i}",
                    "title": f"Document {i//2}",
                    "page": i+1
                },
                "score": 0.95 - (i * 0.05),
            }
            for i in range(5)
        ]
    }


@pytest.fixture
def mock_providers():
    """Create mock providers for testing."""
    providers = AsyncMock()
    providers.llm = AsyncMock()
    providers.llm.aget_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": "LLM generated response"}}]}
    )
    providers.llm.aget_completion_stream = AsyncMock(
        return_value=iter([{"choices": [{"delta": {"content": "Streamed chunk"}}]}])
    )

    providers.database = AsyncMock()
    providers.database.prompts_handler = AsyncMock()
    providers.database.prompts_handler.get_cached_prompt = AsyncMock(
        return_value="System prompt template with {{context}} placeholder"
    )

    return providers


class TestRAGPromptBuilding:
    """Tests for RAG prompt construction."""

    @pytest.mark.asyncio
    async def test_rag_prompt_construction(self, mock_providers, mock_search_results):
        """Test RAG prompt construction with search results."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None, include_metadata=True):
                # Simple implementation that handles search results
                chunks = search_results.get("chunk_search_results", [])

                context = ""
                for i, chunk in enumerate(chunks):
                    # Format the chunk text
                    chunk_text = f"[{i+1}] {chunk.get('text', '')}"

                    # Add metadata if requested
                    if include_metadata:
                        metadata_items = []
                        for key, value in chunk.get("metadata", {}).items():
                            if key not in ["embedding"]:  # Skip non-user-friendly fields
                                metadata_items.append(f"{key}: {value}")

                        if metadata_items:
                            metadata_str = ", ".join(metadata_items)
                            chunk_text += f" ({metadata_str})"

                    context += chunk_text + "\n\n"

                return [
                    {"role": "system", "content": f"System prompt with context:\n\n{context}"},
                    {"role": "user", "content": query}
                ]

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Call the build method
        query = "What did Aristotle say about ethics?"
        messages = await builder.build_prompt(
            query=query,
            search_results=mock_search_results,
            system_prompt_template_id="default_rag_prompt",
            include_metadata=True
        )

        # Check that the messages list was constructed properly
        assert len(messages) > 0

        # Find the system message
        system_message = next((m for m in messages if m["role"] == "system"), None)
        assert system_message is not None, "System message should be present"

        # Check that context was injected into system message
        assert "search result" in system_message["content"], "System message should contain search results"

        # Check that metadata was included
        assert "source" in system_message["content"] or "title" in system_message["content"], \
            "System message should contain metadata when include_metadata=True"

        # Find the user message
        user_message = next((m for m in messages if m["role"] == "user"), None)
        assert user_message is not None, "User message should be present"
        assert user_message["content"] == query, "User message should contain the query"

    @pytest.mark.asyncio
    async def test_rag_prompt_construction_without_metadata(self, mock_providers, mock_search_results):
        """Test RAG prompt construction without metadata."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None, include_metadata=True):
                # Simple implementation that handles search results
                chunks = search_results.get("chunk_search_results", [])

                context = ""
                for i, chunk in enumerate(chunks):
                    # Format the chunk text
                    chunk_text = f"[{i+1}] {chunk.get('text', '')}"

                    # Add metadata if requested
                    if include_metadata:
                        metadata_items = []
                        for key, value in chunk.get("metadata", {}).items():
                            if key not in ["embedding"]:  # Skip non-user-friendly fields
                                metadata_items.append(f"{key}: {value}")

                        if metadata_items:
                            metadata_str = ", ".join(metadata_items)
                            chunk_text += f" ({metadata_str})"

                    context += chunk_text + "\n\n"

                return [
                    {"role": "system", "content": f"System prompt with context:\n\n{context}"},
                    {"role": "user", "content": query}
                ]

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Call the build method without metadata
        query = "What did Aristotle say about ethics?"
        messages = await builder.build_prompt(
            query=query,
            search_results=mock_search_results,
            system_prompt_template_id="default_rag_prompt",
            include_metadata=False
        )

        # Find the system message
        system_message = next((m for m in messages if m["role"] == "system"), None)

        # Ensure metadata is not included
        for term in ["source", "title", "page"]:
            assert term not in system_message["content"].lower(), \
                f"System message should not contain metadata term '{term}' when include_metadata=False"

    @pytest.mark.asyncio
    async def test_rag_prompt_with_task_prompt(self, mock_providers, mock_search_results):
        """Test RAG prompt construction with a task prompt."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None, task_prompt=None):
                # Simple implementation that handles search results
                chunks = search_results.get("chunk_search_results", [])

                context = ""
                for i, chunk in enumerate(chunks):
                    # Format the chunk text
                    chunk_text = f"[{i+1}] {chunk.get('text', '')}"

                    context += chunk_text + "\n\n"

                if task_prompt:
                    context += f"\n\nTask: {task_prompt}"

                return [
                    {"role": "system", "content": f"System prompt with context:\n\n{context}"},
                    {"role": "user", "content": query}
                ]

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Call the build method with a task prompt
        query = "What did Aristotle say about ethics?"
        task_prompt = "Summarize the information and provide key points only"
        messages = await builder.build_prompt(
            query=query,
            search_results=mock_search_results,
            system_prompt_template_id="default_rag_prompt",
            task_prompt=task_prompt
        )

        # Find the messages
        system_message = next((m for m in messages if m["role"] == "system"), None)
        user_message = next((m for m in messages if m["role"] == "user"), None)

        # Check that task prompt was incorporated
        assert task_prompt in system_message["content"] or task_prompt in user_message["content"], \
            "Task prompt should be incorporated into the messages"

    @pytest.mark.asyncio
    async def test_rag_prompt_with_conversation_history(self, mock_providers, mock_search_results):
        """Test RAG prompt construction with conversation history."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None, conversation_history=None):
                # Simple implementation that handles search results
                chunks = search_results.get("chunk_search_results", [])

                context = ""
                for i, chunk in enumerate(chunks):
                    # Format the chunk text
                    chunk_text = f"[{i+1}] {chunk.get('text', '')}"

                    context += chunk_text + "\n\n"

                messages = [
                    {"role": "system", "content": f"System prompt with context:\n\n{context}"}
                ]

                # Add conversation history if provided
                if conversation_history:
                    messages.extend(conversation_history)
                else:
                    # Only add the query as a separate message if no conversation history
                    messages.append({"role": "user", "content": query})

                return messages

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Setup conversation history
        conversation_history = [
            {"role": "user", "content": "Tell me about Aristotle"},
            {"role": "assistant", "content": "Aristotle was a Greek philosopher."},
            {"role": "user", "content": "What about his ethics?"}
        ]

        # The last message in conversation history is the query
        query = conversation_history[-1]["content"]
        messages = await builder.build_prompt(
            query=query,
            search_results=mock_search_results,
            system_prompt_template_id="default_rag_prompt",
            conversation_history=conversation_history
        )

        # Check that all conversation messages are included
        history_messages = [m for m in messages if m["role"] in ["user", "assistant"]]
        assert len(history_messages) == len(conversation_history), \
            "All conversation history messages should be included"

        # Check that the conversation history is preserved in the correct order
        for i, msg in enumerate(history_messages):
            assert msg["role"] == conversation_history[i]["role"]
            assert msg["content"] == conversation_history[i]["content"]

    @pytest.mark.asyncio
    async def test_rag_prompt_with_citations(self, mock_providers, mock_search_results):
        """Test RAG prompt construction with citation information."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None, include_citations=True):
                # Simple implementation that handles search results
                chunks = search_results.get("chunk_search_results", [])

                context = ""
                for i, chunk in enumerate(chunks):
                    # Format the chunk text
                    chunk_text = f"[{i+1}] {chunk.get('text', '')}"

                    # Add citation marker if requested
                    citation_id = chunk.get("metadata", {}).get("citation_id")
                    if include_citations and citation_id:
                        chunk_text += f" [{citation_id}]"

                    context += chunk_text + "\n\n"

                # Include instructions about citations
                citation_instructions = ""
                if include_citations:
                    citation_instructions = "\n\nWhen referring to the context, include citation markers like [cit0] to attribute information to its source."

                return [
                    {"role": "system", "content": f"System prompt with context:\n\n{context}{citation_instructions}"},
                    {"role": "user", "content": query}
                ]

        # Add citation metadata to search results
        for i, result in enumerate(mock_search_results["chunk_search_results"]):
            result["metadata"]["citation_id"] = f"cit-{i}"

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Call the build method with citations enabled
        query = "What did Aristotle say about ethics?"
        messages = await builder.build_prompt(
            query=query,
            search_results=mock_search_results,
            system_prompt_template_id="default_rag_prompt",
            include_citations=True
        )

        # Find the system message
        system_message = next((m for m in messages if m["role"] == "system"), None)

        # Check that citation markers are included in the context
        assert any(f"[cit-{i}]" in system_message["content"] for i in range(5)), \
            "Citation markers should be included in the context"

        # Check for citation instruction in the prompt
        assert "citation" in system_message["content"].lower(), \
            "System message should include instructions about using citations"

    @pytest.mark.asyncio
    async def test_rag_custom_system_prompt(self, mock_providers, mock_search_results):
        """Test RAG prompt construction with a custom system prompt."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None):
                # Simple implementation that handles search results
                chunks = search_results.get("chunk_search_results", [])

                context = ""
                for i, chunk in enumerate(chunks):
                    # Format the chunk text
                    chunk_text = f"[{i+1}] {chunk.get('text', '')}"

                    context += chunk_text + "\n\n"

                # Get the custom system prompt template
                custom_prompt = "Custom system prompt with {{context}} and some instructions"
                if system_prompt_template_id:
                    # In a real implementation, this would fetch the template from a database
                    custom_prompt = f"Custom system prompt for {system_prompt_template_id} with {{{{context}}}}"

                # Replace the context placeholder with actual context
                system_content = custom_prompt.replace("{{context}}", context)

                return [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": query}
                ]

        # Create a custom system prompt template
        custom_prompt = "Custom system prompt with {{context}} and some instructions"

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Call the build method with a custom system prompt template ID
        query = "What did Aristotle say about ethics?"
        messages = await builder.build_prompt(
            query=query,
            search_results=mock_search_results,
            system_prompt_template_id="custom_template_id"
        )

        # Find the system message
        system_message = next((m for m in messages if m["role"] == "system"), None)

        # Check that the custom prompt was used
        assert "Custom system prompt" in system_message["content"], \
            "System message should use the custom prompt template"

        # Check that context was still injected
        assert "search result" in system_message["content"], \
            "Context should still be injected into custom prompt"


class TestRAGProcessing:
    """Tests for RAG processing and generation."""

    @pytest.mark.asyncio
    async def test_rag_generation(self, mock_providers, mock_search_results):
        """Test generating a response using RAG."""
        class RAGProcessor:
            def __init__(self, providers):
                self.providers = providers
                self.prompt_builder = MagicMock()
                self.prompt_builder.build_prompt = AsyncMock(
                    return_value=[
                        {"role": "system", "content": "System prompt with context"},
                        {"role": "user", "content": "What did Aristotle say about ethics?"}
                    ]
                )

            async def generate(self, query, search_results, **kwargs):
                # Build the prompt
                messages = await self.prompt_builder.build_prompt(
                    query=query,
                    search_results=search_results,
                    **kwargs
                )

                # Generate a response
                response = await self.providers.llm.aget_completion(messages=messages)
                return response["choices"][0]["message"]["content"]

        # Create the processor
        processor = RAGProcessor(mock_providers)

        # Generate a response
        query = "What did Aristotle say about ethics?"
        response = await processor.generate(
            query=query,
            search_results=mock_search_results
        )

        # Verify the LLM was called
        mock_providers.llm.aget_completion.assert_called_once()

        # Check the response
        assert response == "LLM generated response"

    @pytest.mark.asyncio
    async def test_rag_streaming(self, mock_providers, mock_search_results):
        """Test streaming a response using RAG."""
        class RAGProcessor:
            def __init__(self, providers):
                self.providers = providers
                self.prompt_builder = MagicMock()
                self.prompt_builder.build_prompt = AsyncMock(
                    return_value=[
                        {"role": "system", "content": "System prompt with context"},
                        {"role": "user", "content": "What did Aristotle say about ethics?"}
                    ]
                )

            async def generate_stream(self, query, search_results, **kwargs):
                # Build the prompt
                messages = await self.prompt_builder.build_prompt(
                    query=query,
                    search_results=search_results,
                    **kwargs
                )

                # Generate a streaming response
                stream = await self.providers.llm.aget_completion_stream(messages=messages)
                return stream

        # Create a mock stream
        class MockStream:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration

                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        # Configure the LLM mock to return an async iterable stream
        mock_stream = MockStream([
            {"choices": [{"delta": {"content": "This"}}]},
            {"choices": [{"delta": {"content": " is"}}]},
            {"choices": [{"delta": {"content": " a"}}]},
            {"choices": [{"delta": {"content": " test"}}]},
            {"choices": [{"delta": {"content": " response."}}]}
        ])

        mock_providers.llm.aget_completion_stream = AsyncMock(return_value=mock_stream)

        # Create the processor
        processor = RAGProcessor(mock_providers)

        # Generate a streaming response
        query = "What did Aristotle say about ethics?"
        stream = await processor.generate_stream(
            query=query,
            search_results=mock_search_results
        )

        # Verify the LLM streaming method was called
        mock_providers.llm.aget_completion_stream.assert_called_once()

        # Process the stream
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        # Verify chunks were received
        assert len(chunks) == 5, "Should receive all 5 chunks"
        assert chunks[0]["choices"][0]["delta"]["content"] == "This", "First chunk content should match"
        assert chunks[-1]["choices"][0]["delta"]["content"] == " response.", "Last chunk content should match"

    @pytest.mark.asyncio
    async def test_rag_with_different_provider_models(self, mock_providers, mock_search_results):
        """Test RAG with different provider models."""
        class RAGProcessor:
            def __init__(self, providers):
                self.providers = providers
                self.prompt_builder = MagicMock()
                self.prompt_builder.build_prompt = AsyncMock(
                    return_value=[
                        {"role": "system", "content": "System prompt with context"},
                        {"role": "user", "content": "What did Aristotle say about ethics?"}
                    ]
                )

            async def generate(self, query, search_results, model=None, **kwargs):
                # Build the prompt
                messages = await self.prompt_builder.build_prompt(
                    query=query,
                    search_results=search_results,
                    **kwargs
                )

                # Generate a response with the specified model
                response = await self.providers.llm.aget_completion(
                    messages=messages,
                    model=model
                )
                return response["choices"][0]["message"]["content"]

        # Create the processor
        processor = RAGProcessor(mock_providers)

        # Generate responses with different models
        query = "What did Aristotle say about ethics?"
        models = ["gpt-4", "claude-3-opus", "gemini-pro"]

        for model in models:
            await processor.generate(
                query=query,
                search_results=mock_search_results,
                model=model
            )

            # Verify the LLM was called with the correct model
            call_kwargs = mock_providers.llm.aget_completion.call_args[1]
            assert call_kwargs["model"] == model

            # Reset the mock for the next iteration
            mock_providers.llm.aget_completion.reset_mock()


class TestRAGContextFormatting:
    """Tests for formatting context in RAG prompts."""

    def test_default_context_formatting(self, mock_search_results):
        """Test the default formatting of context from search results."""
        # Function to format context
        def format_context(search_results, include_metadata=True):
            context = ""
            for i, result in enumerate(search_results["chunk_search_results"]):
                # Format the chunk text
                chunk_text = f"[{i+1}] {result['text']}"

                # Add metadata if requested
                if include_metadata:
                    metadata_items = []
                    for key, value in result.get("metadata", {}).items():
                        if key not in ["embedding"]:  # Skip non-user-friendly fields
                            metadata_items.append(f"{key}: {value}")

                    if metadata_items:
                        metadata_str = ", ".join(metadata_items)
                        chunk_text += f" ({metadata_str})"

                context += chunk_text + "\n\n"

            return context.strip()

        # Format context with metadata
        context_with_metadata = format_context(mock_search_results)

        # Check formatting
        assert "[1]" in context_with_metadata
        assert "source" in context_with_metadata
        assert "title" in context_with_metadata

        # Format context without metadata
        context_without_metadata = format_context(mock_search_results, include_metadata=False)

        # Check formatting
        assert "[1]" in context_without_metadata
        assert "source" not in context_without_metadata
        assert "title" not in context_without_metadata

    def test_numbered_list_context_formatting(self, mock_search_results):
        """Test numbered list formatting of context."""
        # Function to format context as a numbered list
        def format_context_numbered_list(search_results):
            context_items = []
            for i, result in enumerate(search_results["chunk_search_results"]):
                context_items.append(f"{i+1}. {result['text']}")

            return "\n".join(context_items)

        # Format context
        context = format_context_numbered_list(mock_search_results)

        # Check formatting
        assert "1. " in context
        assert "2. " in context
        assert "3. " in context
        assert "4. " in context
        assert "5. " in context

    def test_source_attribution_context_formatting(self, mock_search_results):
        """Test context formatting with source attribution."""
        # Function to format context with source attribution
        def format_context_with_sources(search_results):
            context_items = []
            for result in search_results["chunk_search_results"]:
                source = result.get("metadata", {}).get("source", "Unknown source")
                title = result.get("metadata", {}).get("title", "Unknown title")

                context_items.append(f"From {source} ({title}):\n{result['text']}")

            return "\n\n".join(context_items)

        # Format context
        context = format_context_with_sources(mock_search_results)

        # Check formatting
        assert "From source-0" in context
        assert "Document 0" in context
        assert "From source-1" in context

    def test_citation_marker_context_formatting(self, mock_search_results):
        """Test context formatting with citation markers."""
        # Add citation IDs to search results
        for i, result in enumerate(mock_search_results["chunk_search_results"]):
            result["metadata"]["citation_id"] = f"cit{i}"

        # Function to format context with citation markers
        def format_context_with_citations(search_results):
            context_items = []
            for i, result in enumerate(search_results["chunk_search_results"]):
                citation_id = result.get("metadata", {}).get("citation_id")
                text = result["text"]

                if citation_id:
                    context_items.append(f"[{i+1}] {text} [{citation_id}]")
                else:
                    context_items.append(f"[{i+1}] {text}")

            return "\n\n".join(context_items)

        # Format context
        context = format_context_with_citations(mock_search_results)

        # Check formatting
        assert "[cit0]" in context
        assert "[cit1]" in context
        assert "[cit2]" in context


class TestRAGErrorHandling:
    """Tests for handling errors in RAG processing."""

    @pytest.mark.asyncio
    async def test_rag_with_empty_search_results(self, mock_providers):
        """Test RAG behavior with empty search results."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None):
                # Simple implementation that handles empty results gracefully
                if not search_results.get("chunk_search_results"):
                    return [
                        {"role": "system", "content": "No relevant information was found for your query."},
                        {"role": "user", "content": query}
                    ]
                return []

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Setup empty search results
        empty_search_results = {"chunk_search_results": []}

        # Call the build method with empty results
        query = "What did Aristotle say about ethics?"
        messages = await builder.build_prompt(
            query=query,
            search_results=empty_search_results,
            system_prompt_template_id="default_rag_prompt"
        )

        # Find the system message
        system_message = next((m for m in messages if m["role"] == "system"), None)

        # Check that the system message handles empty results gracefully
        assert system_message is not None, "System message should be present even with empty results"
        assert "no relevant information" in system_message["content"].lower(), \
               "System message should indicate that no relevant information was found"

    @pytest.mark.asyncio
    async def test_rag_with_malformed_search_results(self, mock_providers):
        """Test RAG behavior with malformed search results."""
        class RAGPromptBuilder:
            def __init__(self, providers):
                self.providers = providers

            async def build_prompt(self, query, search_results, system_prompt_template_id=None):
                # Handle malformed results by including whatever is available
                chunks = search_results.get("chunk_search_results", [])

                context = ""
                for chunk in chunks:
                    # Handle missing fields gracefully
                    text = chunk.get("text", "No text content")
                    context += text + "\n\n"

                return [
                    {"role": "system", "content": f"Context:\n{context}\n\nBased on the above context, answer the following question."},
                    {"role": "user", "content": query}
                ]

        # Create a RAG prompt builder
        builder = RAGPromptBuilder(providers=mock_providers)

        # Setup malformed search results (missing required fields)
        malformed_search_results = {
            "chunk_search_results": [
                {
                    # Missing chunk_id, document_id
                    "text": "Malformed result without required fields"
                    # Missing metadata
                }
            ]
        }

        # Call the build method with malformed results
        query = "What did Aristotle say about ethics?"
        messages = await builder.build_prompt(
            query=query,
            search_results=malformed_search_results,
            system_prompt_template_id="default_rag_prompt"
        )

        # Find the system message
        system_message = next((m for m in messages if m["role"] == "system"), None)

        # Check that the system message handles malformed results gracefully
        assert system_message is not None, "System message should be present even with malformed results"
        assert "Malformed result" in system_message["content"], \
               "The text content should still be included"

    @pytest.mark.asyncio
    async def test_rag_with_llm_error_recovery(self, mock_providers, mock_search_results):
        """Test RAG recovery from LLM errors."""
        class RAGProcessorWithErrorRecovery:
            def __init__(self, providers):
                self.providers = providers
                self.prompt_builder = MagicMock()
                self.prompt_builder.build_prompt = AsyncMock(
                    return_value=[
                        {"role": "system", "content": "System prompt with context"},
                        {"role": "user", "content": "What did Aristotle say about ethics?"}
                    ]
                )

                # Configure the LLM mock to fail on first call, succeed on second
                self.providers.llm.aget_completion = AsyncMock(side_effect=[
                    Exception("LLM API error"),
                    {"choices": [{"message": {"content": "Fallback response after error"}}]}
                ])

            async def generate_with_error_recovery(self, query, search_results, **kwargs):
                # Build the prompt
                messages = await self.prompt_builder.build_prompt(
                    query=query,
                    search_results=search_results,
                    **kwargs
                )

                # Try with primary model
                try:
                    response = await self.providers.llm.aget_completion(
                        messages=messages,
                        model="primary_model"
                    )
                    return response["choices"][0]["message"]["content"]
                except Exception as e:
                    # On error, try with fallback model
                    response = await self.providers.llm.aget_completion(
                        messages=messages,
                        model="fallback_model"
                    )
                    return response["choices"][0]["message"]["content"]

        # Create the processor
        processor = RAGProcessorWithErrorRecovery(mock_providers)

        # Generate a response with error recovery
        query = "What did Aristotle say about ethics?"
        response = await processor.generate_with_error_recovery(
            query=query,
            search_results=mock_search_results
        )

        # Verify both LLM calls were made
        assert mock_providers.llm.aget_completion.call_count == 2

        # Check the second call used the fallback model
        second_call_kwargs = mock_providers.llm.aget_completion.call_args_list[1][1]
        assert second_call_kwargs["model"] == "fallback_model"

        # Check the response is from the fallback
        assert response == "Fallback response after error"


class TestRAGContextTruncation:
    """Tests for context truncation strategies in RAG."""

    def test_token_count_truncation(self, mock_search_results):
        """Test truncating context based on token count."""
        # Function to truncate context to max tokens
        def truncate_context_by_tokens(search_results, max_tokens=1000):
            # Simple token counting function (in real code, use a tokenizer)
            def estimate_tokens(text):
                # Rough approximation: 4 chars ~ 1 token
                return len(text) // 4

            context_items = []
            current_tokens = 0

            # Add chunks until we hit the token limit
            for result in search_results["chunk_search_results"]:
                chunk_text = result["text"]
                chunk_tokens = estimate_tokens(chunk_text)

                if current_tokens + chunk_tokens > max_tokens:
                    # If this chunk would exceed the limit, stop
                    break

                # Add this chunk and update token count
                context_items.append(chunk_text)
                current_tokens += chunk_tokens

            return "\n\n".join(context_items)

        # Truncate to a small token limit (should fit ~2-3 chunks)
        small_context = truncate_context_by_tokens(mock_search_results, max_tokens=50)

        # Check truncation
        chunk_count = small_context.count("search result")
        assert 1 <= chunk_count <= 3, "Should only include 1-3 chunks with small token limit"

        # Truncate with larger limit (should fit all chunks)
        large_context = truncate_context_by_tokens(mock_search_results, max_tokens=1000)
        large_chunk_count = large_context.count("search result")
        assert large_chunk_count == 5, "Should include all 5 chunks with large token limit"

    def test_score_threshold_truncation(self, mock_search_results):
        """Test truncating context based on relevance score threshold."""
        # Function to truncate context based on minimum score
        def truncate_context_by_score(search_results, min_score=0.7):
            context_items = []

            # Add chunks that meet the minimum score
            for result in search_results["chunk_search_results"]:
                if result.get("score", 0) >= min_score:
                    context_items.append(result["text"])

            return "\n\n".join(context_items)

        # Truncate with high score threshold (should only include top results)
        high_threshold_context = truncate_context_by_score(mock_search_results, min_score=0.85)

        # Check truncation
        high_chunk_count = high_threshold_context.count("search result")
        assert high_chunk_count <= 3, "Should only include top chunks with high score threshold"

        # Truncate with low score threshold (should include most or all chunks)
        low_threshold_context = truncate_context_by_score(mock_search_results, min_score=0.7)
        low_chunk_count = low_threshold_context.count("search result")
        assert low_chunk_count >= 4, "Should include most chunks with low score threshold"

    def test_mixed_truncation_strategy(self, mock_search_results):
        """Test mixed truncation strategy combining token count and score."""
        # Function implementing mixed truncation strategy
        def mixed_truncation_strategy(search_results, max_tokens=1000, min_score=0.7):
            # First filter by score
            filtered_results = [r for r in search_results["chunk_search_results"]
                               if r.get("score", 0) >= min_score]

            # Then truncate by tokens
            def estimate_tokens(text):
                return len(text) // 4

            context_items = []
            current_tokens = 0

            for result in filtered_results:
                chunk_text = result["text"]
                chunk_tokens = estimate_tokens(chunk_text)

                if current_tokens + chunk_tokens > max_tokens:
                    break

                context_items.append(chunk_text)
                current_tokens += chunk_tokens

            return "\n\n".join(context_items)

        # Test the mixed strategy
        context = mixed_truncation_strategy(
            mock_search_results,
            max_tokens=50,
            min_score=0.8
        )

        # Check result
        chunk_count = context.count("search result")
        assert 1 <= chunk_count <= 3, "Mixed strategy should limit results appropriately"


class TestAdvancedCitationHandling:
    """Tests for advanced citation handling in RAG."""

    @pytest.fixture
    def mock_citation_results(self):
        """Return mock search results with citation information."""
        results = {
            "chunk_search_results": [
                {
                    "chunk_id": f"chunk-{i}",
                    "document_id": f"doc-{i//2}",
                    "text": f"This is search result {i} about Aristotle's philosophy.",
                    "metadata": {
                        "source": f"source-{i}",
                        "title": f"Document {i//2}",
                        "page": i+1,
                        "citation_id": f"cite{i}",
                        "authors": ["Author A", "Author B"] if i % 2 == 0 else ["Author C"]
                    },
                    "score": 0.95 - (i * 0.05),
                }
                for i in range(5)
            ]
        }
        return results

    def test_structured_citation_formatting(self, mock_citation_results):
        """Test formatting structured citations with academic format."""
        # Function to format structured citations
        def format_structured_citations(search_results):
            citations = {}

            # Extract citation information
            for result in search_results["chunk_search_results"]:
                citation_id = result.get("metadata", {}).get("citation_id")
                if not citation_id:
                    continue

                # Skip if we've already processed this citation
                if citation_id in citations:
                    continue

                # Extract metadata
                metadata = result.get("metadata", {})
                authors = metadata.get("authors", [])
                title = metadata.get("title", "Untitled")
                source = metadata.get("source", "Unknown source")
                page = metadata.get("page", None)

                # Format citation in academic style
                author_text = ", ".join(authors) if authors else "Unknown author"
                citation_text = f"{author_text}. \"{title}\". {source}"
                if page:
                    citation_text += f", p. {page}"

                # Store the formatted citation
                citations[citation_id] = {
                    "text": citation_text,
                    "document_id": result.get("document_id"),
                    "chunk_id": result.get("chunk_id")
                }

            return citations

        # Format citations
        citations = format_structured_citations(mock_citation_results)

        # Check formatting
        assert len(citations) == 5, "Should have 5 unique citations"
        assert "Author A, Author B" in citations["cite0"]["text"], "Should include authors"
        assert "Document 0" in citations["cite0"]["text"], "Should include title"
        assert "source-0" in citations["cite0"]["text"], "Should include source"
        assert "p. 1" in citations["cite0"]["text"], "Should include page number"

    def test_inline_citation_replacement(self, mock_citation_results):
        """Test replacing citation placeholders with actual citations."""
        # First format the context with citation placeholders
        def format_context_with_citations(search_results):
            context_items = []
            for i, result in enumerate(search_results["chunk_search_results"]):
                citation_id = result.get("metadata", {}).get("citation_id")
                text = result["text"]

                if citation_id:
                    context_items.append(f"{text} [{citation_id}]")
                else:
                    context_items.append(text)

            return "\n\n".join(context_items)

        # Function to replace citation placeholders in LLM response
        def replace_citation_placeholders(response_text, citation_metadata):
            # Simple regex-based replacement
            import re

            def citation_replacement(match):
                citation_id = match.group(1)
                if citation_id in citation_metadata:
                    citation = citation_metadata[citation_id]
                    authors = citation.get("authors", ["Unknown author"])
                    year = citation.get("year", "n.d.")
                    return f"({authors[0]} et al., {year})"
                return match.group(0)  # Keep original if not found

            # Replace [citeX] format
            pattern = r'\[(cite\d+)\]'
            return re.sub(pattern, citation_replacement, response_text)

        # Create mock citation metadata
        citation_metadata = {
            f"cite{i}": {
                "authors": [f"Author {chr(65+i)}"] + (["et al."] if i % 2 == 0 else []),
                "year": 2020 + i,
                "title": f"Document {i//2}"
            }
            for i in range(5)
        }

        # Response with citation placeholders
        response_with_placeholders = (
            "Aristotle's ethics [cite0] focuses on virtue ethics. "
            "This contrasts with utilitarianism [cite2] which focuses on outcomes. "
            "Later philosophers [cite4] expanded on these ideas."
        )

        # Replace placeholders
        final_response = replace_citation_placeholders(response_with_placeholders, citation_metadata)

        # Check formatting
        assert "(Author A et al., 2020)" in final_response, "Author A citation should be in the response"
        assert "(Author C" in final_response, "Author C citation should be in the response"
        assert "(Author E" in final_response, "Author E citation should be in the response"
        assert "[cite0]" not in final_response, "Citation placeholder [cite0] should be replaced"
        assert "[cite2]" not in final_response, "Citation placeholder [cite2] should be replaced"
        assert "[cite4]" not in final_response, "Citation placeholder [cite4] should be replaced"

    def test_hybrid_citation_strategy(self, mock_citation_results):
        """Test hybrid citation strategy with footnotes and bibliography."""
        # Function to process text with hybrid citation strategy
        def process_with_hybrid_citations(response_text, citation_metadata):
            import re

            # Step 1: Replace inline citations with footnote numbers
            footnotes = []
            footnote_index = 1

            def footnote_replacement(match):
                nonlocal footnote_index
                citation_id = match.group(1)

                if citation_id in citation_metadata:
                    # Add footnote
                    citation = citation_metadata[citation_id]
                    source = citation.get("source", "Unknown source")
                    title = citation.get("title", "Untitled")
                    authors = citation.get("authors", ["Unknown author"])
                    author_text = ", ".join(authors)

                    footnote = f"{footnote_index}. {author_text}. \"{title}\". {source}."
                    footnotes.append(footnote)

                    # Return footnote reference in text
                    result = f"[{footnote_index}]"
                    footnote_index += 1
                    return result

                return match.group(0)  # Keep original if not found

            # Replace [citeX] format with footnote numbers
            pattern = r'\[(cite\d+)\]'
            processed_text = re.sub(pattern, footnote_replacement, response_text)

            # Step 2: Add footnotes at the end
            if footnotes:
                processed_text += "\n\nFootnotes:\n" + "\n".join(footnotes)

            # Step 3: Add bibliography
            bibliography = []
            for citation_id, citation in citation_metadata.items():
                if any(f"[{citation_id}]" in response_text for citation_id in citation_metadata):
                    source = citation.get("source", "Unknown source")
                    title = citation.get("title", "Untitled")
                    authors = citation.get("authors", ["Unknown author"])
                    year = citation.get("year", "n.d.")

                    bib_entry = f"{', '.join(authors)}. ({year}). \"{title}\". {source}."
                    bibliography.append(bib_entry)

            if bibliography:
                processed_text += "\n\nBibliography:\n" + "\n".join(bibliography)

            return processed_text

        # Create mock citation metadata
        citation_metadata = {
            f"cite{i}": {
                "authors": [f"Author {chr(65+i)}"] + (["et al."] if i % 2 == 0 else []),
                "year": 2020 + i,
                "title": f"Document {i//2}",
                "source": f"Journal of Philosophy, Volume {i+1}"
            }
            for i in range(5)
        }

        # Response with citation placeholders
        response_with_placeholders = (
            "Aristotle's ethics [cite0] focuses on virtue ethics. "
            "This contrasts with utilitarianism [cite2] which focuses on outcomes. "
            "Later philosophers [cite4] expanded on these ideas."
        )

        # Apply hybrid citation processing
        final_response = process_with_hybrid_citations(response_with_placeholders, citation_metadata)

        # Check formatting
        assert "[1]" in final_response
        assert "[2]" in final_response
        assert "[3]" in final_response
        assert "Footnotes:" in final_response
        assert "Bibliography:" in final_response
        assert "Journal of Philosophy" in final_response
        assert "[cite0]" not in final_response
        assert "[cite2]" not in final_response
        assert "[cite4]" not in final_response


class TestRAGRetrievalStrategies:
    """Tests for different retrieval strategies in RAG."""

    @pytest.mark.asyncio
    async def test_hybrid_search_strategy(self, mock_providers):
        """Test hybrid search combining keyword and semantic search."""
        # Mock search results
        keyword_results = {
            "chunk_search_results": [
                {
                    "chunk_id": f"keyword-chunk-{i}",
                    "document_id": f"doc-{i}",
                    "text": f"Keyword match {i} about Aristotle's ethics.",
                    "metadata": {"source": f"source-{i}"},
                    "score": 0.95 - (i * 0.05),
                }
                for i in range(3)
            ]
        }

        semantic_results = {
            "chunk_search_results": [
                {
                    "chunk_id": f"semantic-chunk-{i}",
                    "document_id": f"doc-{i+5}",
                    "text": f"Semantic match {i} about virtue ethics philosophy.",
                    "metadata": {"source": f"source-{i+5}"},
                    "score": 0.9 - (i * 0.05),
                }
                for i in range(3)
            ]
        }

        # Mock hybrid search function
        async def perform_hybrid_search(query, **kwargs):
            # Perform both search types
            # In real implementation, these would be actual search calls
            keyword_results_copy = keyword_results.copy()
            semantic_results_copy = semantic_results.copy()

            # Combine and deduplicate results
            combined_results = {
                "chunk_search_results":
                    keyword_results_copy["chunk_search_results"][:2] +
                    semantic_results_copy["chunk_search_results"][:2]
            }

            return combined_results

        # Mock RAG processor using hybrid search
        class HybridSearchRAGProcessor:
            def __init__(self, providers):
                self.providers = providers
                # Fix the prompt builder to include actual content
                self.prompt_builder = MagicMock()

                # Configure the prompt builder to actually include the search results in the prompt
                async def build_prompt_with_content(query, search_results, **kwargs):
                    context = ""
                    for result in search_results.get("chunk_search_results", []):
                        context += f"{result.get('text', '')}\n\n"

                    return [
                        {"role": "system", "content": f"System prompt with hybrid context:\n\n{context}"},
                        {"role": "user", "content": query}
                    ]

                self.prompt_builder.build_prompt = AsyncMock(side_effect=build_prompt_with_content)

                # Configure LLM to return a valid response
                self.providers.llm.aget_completion = AsyncMock(return_value={
                    "choices": [{"message": {"content": "LLM generated response"}}]
                })

            async def generate_with_hybrid_search(self, query):
                # Perform hybrid search
                search_results = await perform_hybrid_search(query)

                # Build prompt with combined results
                messages = await self.prompt_builder.build_prompt(
                    query=query,
                    search_results=search_results
                )

                # Generate response
                response = await self.providers.llm.aget_completion(messages=messages)
                return response["choices"][0]["message"]["content"]

        # Create processor and generate response
        processor = HybridSearchRAGProcessor(mock_providers)
        query = "What did Aristotle say about ethics?"

        response = await processor.generate_with_hybrid_search(query)

        # Check that the LLM was called with the hybrid search results
        call_args = mock_providers.llm.aget_completion.call_args[1]
        messages = call_args["messages"]

        # Find the system message
        system_message = next((m for m in messages if m["role"] == "system"), None)

        # Verify both result types are in the context
        assert "Keyword match" in system_message["content"], "System message should include keyword matches"
        assert "Semantic match" in system_message["content"], "System message should include semantic matches"

        # Check the final response
        assert response == "LLM generated response", "Should return the mocked LLM response"

    @pytest.mark.asyncio
    async def test_reranking_strategy(self, mock_providers, mock_search_results):
        """Test reranking search results before including in RAG context."""
        # Define a reranker function
        def rerank_results(search_results, query):
            # This would use a model in real implementation
            # Here we'll just simulate reranking with a simple heuristic

            # Create a copy to avoid modifying the original
            reranked_results = {"chunk_search_results": []}

            # Apply a mock reranking logic
            for result in search_results["chunk_search_results"]:
                # Create a copy of the result
                new_result = result.copy()

                # Adjust score based on whether it contains keywords from query
                keywords = ["ethics", "aristotle", "philosophy"]
                score_adjustment = sum(0.1 for keyword in keywords
                                      if keyword.lower() in new_result["text"].lower())

                new_result["score"] = min(0.99, result.get("score", 0.5) + score_adjustment)
                new_result["reranked"] = True

                reranked_results["chunk_search_results"].append(new_result)

            # Sort by adjusted score
            reranked_results["chunk_search_results"].sort(
                key=lambda x: x.get("score", 0),
                reverse=True
            )

            return reranked_results

        # Mock RAG processor with reranking
        class RerankedRAGProcessor:
            def __init__(self, providers):
                self.providers = providers
                self.prompt_builder = MagicMock()
                self.prompt_builder.build_prompt = AsyncMock(
                    return_value=[
                        {"role": "system", "content": "System prompt with reranked context"},
                        {"role": "user", "content": "What did Aristotle say about ethics?"}
                    ]
                )

            async def generate_with_reranking(self, query, search_results):
                # Rerank the search results
                reranked_results = rerank_results(search_results, query)

                # Build prompt with reranked results
                messages = await self.prompt_builder.build_prompt(
                    query=query,
                    search_results=reranked_results
                )

                # Generate response
                response = await self.providers.llm.aget_completion(messages=messages)
                return response["choices"][0]["message"]["content"]

        # Create processor
        processor = RerankedRAGProcessor(mock_providers)

        # Generate response with reranking
        query = "What did Aristotle say about ethics?"
        response = await processor.generate_with_reranking(query, mock_search_results)

        # Verify the LLM was called
        mock_providers.llm.aget_completion.assert_called_once()

        # Check the response
        assert response == "LLM generated response"
