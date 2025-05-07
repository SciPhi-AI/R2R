from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from shared.api.models import (
    CitationEvent,
    FinalAnswerEvent,
    MessageEvent,
    SearchResultsEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    UnknownEvent,
    WrappedAgentResponse,
    WrappedEmbeddingResponse,
    WrappedLLMChatCompletion,
    WrappedRAGResponse,
    WrappedSearchResponse,
)

from ..models import (
    GenerationConfig,
    Message,
    SearchMode,
    SearchSettings,
)
from ..sync_methods.retrieval import parse_retrieval_event


class RetrievalSDK:
    """
    SDK for interacting with documents in the v3 API (Asynchronous).
    """

    def __init__(self, client):
        self.client = client

    async def search(
        self,
        query: str,
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
    ) -> WrappedSearchResponse:
        """
        Conduct a vector and/or graph search (async).

        Args:
            query (str): The search query.
            search_mode (Optional[str | SearchMode]): Search mode ('basic', 'advanced', 'custom'). Defaults to 'custom'.
            search_settings (Optional[dict | SearchSettings]): Search settings (filters, limits, hybrid options, etc.).

        Returns:
            WrappedSearchResponse: The search results.
        """
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data: dict[str, Any] = {
            "query": query,
            "search_settings": search_settings,
        }
        if search_mode:
            data["search_mode"] = search_mode

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/search",
            json=data,
            version="v3",
        )
        return WrappedSearchResponse(**response_dict)

    async def completion(
        self,
        messages: list[dict | Message],
        generation_config: Optional[dict | GenerationConfig] = None,
    ) -> WrappedLLMChatCompletion:
        """
        Get a completion from the model (async).

        Args:
            messages (list[dict | Message]): List of messages to generate completion for. Each message should have a 'role' and 'content'.
            generation_config (Optional[dict | GenerationConfig]): Configuration for text generation.

        Returns:
            WrappedLLMChatCompletion
        """
        cast_messages: list[Message] = [
            Message(**msg) if isinstance(msg, dict) else msg
            for msg in messages
        ]
        if generation_config and not isinstance(generation_config, dict):
            generation_config = generation_config.model_dump()

        data: dict[str, Any] = {
            "messages": [msg.model_dump() for msg in cast_messages],
            "generation_config": generation_config,
        }

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/completion",
            json=data,
            version="v3",
        )

        return WrappedLLMChatCompletion(**response_dict)

    async def embedding(self, text: str) -> WrappedEmbeddingResponse:
        """Generate an embedding for given text.

        Args:
            text (str): Text to generate embeddings for.

        Returns:
            WrappedEmbeddingResponse
        """
        data: dict[str, Any] = {
            "text": text,
        }

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/embedding",
            data=data,
            version="v3",
        )

        return WrappedEmbeddingResponse(**response_dict)

    async def rag(
        self,
        query: str,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        search_mode: Optional[str | SearchMode] = SearchMode.custom,
        search_settings: Optional[dict | SearchSettings] = None,
        task_prompt: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        include_web_search: Optional[bool] = False,
    ) -> (
        WrappedRAGResponse
        | AsyncGenerator[
            ThinkingEvent
            | SearchResultsEvent
            | MessageEvent
            | CitationEvent
            | FinalAnswerEvent
            | ToolCallEvent
            | ToolResultEvent
            | UnknownEvent
            | None,
            None,
        ]
    ):
        """Conducts a Retrieval Augmented Generation (RAG) search with the
        given query.

        Args:
            query (str): The query to search for.
            rag_generation_config (Optional[dict | GenerationConfig]): RAG generation configuration.
            search_settings (Optional[dict | SearchSettings]): Vector search settings.
            task_prompt (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            WrappedRAGResponse | AsyncGenerator[RAGResponse, None]: The RAG response
        """
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data: dict[str, Any] = {
            "query": query,
            "rag_generation_config": rag_generation_config,
            "search_settings": search_settings,
            "task_prompt": task_prompt,
            "include_title_if_available": include_title_if_available,
            "include_web_search": include_web_search,
        }

        if search_mode:
            data["search_mode"] = search_mode

        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):

            async def generate_events():
                raw_stream = self.client._make_streaming_request(
                    "POST",
                    "retrieval/rag",
                    json=data,
                    version="v3",
                )
                async for response in raw_stream:
                    yield parse_retrieval_event(response)

            return generate_events()

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/rag",
            json=data,
            version="v3",
        )

        return WrappedRAGResponse(**response_dict)

    async def agent(
        self,
        message: Optional[dict | Message] = None,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        research_generation_config: Optional[dict | GenerationConfig] = None,
        search_mode: Optional[str | SearchMode] = SearchMode.custom,
        search_settings: Optional[dict | SearchSettings] = None,
        task_prompt: Optional[str] = None,
        include_title_if_available: Optional[bool] = True,
        conversation_id: Optional[str | UUID] = None,
        max_tool_context_length: Optional[int] = None,
        use_system_context: Optional[bool] = True,
        rag_tools: Optional[list[str]] = None,
        research_tools: Optional[list[str]] = None,
        tools: Optional[list[str]] = None,
        mode: Optional[str] = "rag",
        needs_initial_conversation_name: Optional[bool] = None,
    ) -> (
        WrappedAgentResponse
        | AsyncGenerator[
            ThinkingEvent
            | SearchResultsEvent
            | MessageEvent
            | CitationEvent
            | FinalAnswerEvent
            | ToolCallEvent
            | ToolResultEvent
            | UnknownEvent
            | None,
            None,
        ]
    ):
        """
        Performs a single turn in a conversation with a RAG agent (async).
        May return a `WrappedAgentResponse` or a streaming generator if `stream=True`.

        Args:
            message (Optional[dict | Message]): Current message to process.
            messages (Optional[list[dict | Message]]): List of messages (deprecated, use message instead).
            rag_generation_config (Optional[dict | GenerationConfig]): Configuration for RAG generation in 'rag' mode.
            research_generation_config (Optional[dict | GenerationConfig]): Configuration for generation in 'research' mode.
            search_mode (Optional[str | SearchMode]): Pre-configured search modes: "basic", "advanced", or "custom".
            search_settings (Optional[dict | SearchSettings]): The search configuration object.
            task_prompt (Optional[str]): Optional custom prompt to override default.
            include_title_if_available (Optional[bool]): Include document titles from search results.
            conversation_id (Optional[str | UUID]): ID of the conversation.
            tools (Optional[list[str]]): List of tools to execute (deprecated).
            rag_tools (Optional[list[str]]): List of tools to enable for RAG mode.
            research_tools (Optional[list[str]]): List of tools to enable for Research mode.
            max_tool_context_length (Optional[int]): Maximum length of returned tool context.
            use_system_context (Optional[bool]): Use extended prompt for generation.
            mode (Optional[Literal["rag", "research"]]): Mode to use for generation: 'rag' or 'research'.

        Returns:
            Either a WrappedAgentResponse or an AsyncGenerator for streaming.
        """
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if research_generation_config and not isinstance(
            research_generation_config, dict
        ):
            research_generation_config = (
                research_generation_config.model_dump()
            )
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data: dict[str, Any] = {
            "rag_generation_config": rag_generation_config or {},
            "search_settings": search_settings,
            "task_prompt": task_prompt,
            "include_title_if_available": include_title_if_available,
            "conversation_id": (
                str(conversation_id) if conversation_id else None
            ),
            "max_tool_context_length": max_tool_context_length,
            "use_system_context": use_system_context,
            "mode": mode,
        }

        # Handle generation configs based on mode
        if research_generation_config and mode == "research":
            data["research_generation_config"] = research_generation_config

        # Handle tool configurations
        if rag_tools:
            data["rag_tools"] = rag_tools
        if research_tools:
            data["research_tools"] = research_tools
        if tools:  # Backward compatibility
            data["tools"] = tools

        if search_mode:
            data["search_mode"] = search_mode

        if needs_initial_conversation_name:
            data["needs_initial_conversation_name"] = (
                needs_initial_conversation_name
            )

        if message:
            cast_message: Message = (
                Message(**message) if isinstance(message, dict) else message
            )
            data["message"] = cast_message.model_dump()

        is_stream = False
        if mode != "research":
            if isinstance(rag_generation_config, dict):
                is_stream = rag_generation_config.get("stream", False)
            elif rag_generation_config is not None:
                is_stream = rag_generation_config.stream
        else:
            if research_generation_config:
                if isinstance(research_generation_config, dict):
                    is_stream = research_generation_config.get(  # type: ignore
                        "stream", False
                    )
                else:
                    is_stream = research_generation_config.stream

        if is_stream:

            async def generate_events():
                raw_stream = self.client._make_streaming_request(
                    "POST",
                    "retrieval/agent",
                    json=data,
                    version="v3",
                )
                async for response in raw_stream:
                    yield parse_retrieval_event(response)

            return generate_events()

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/agent",
            json=data,
            version="v3",
        )
        return WrappedAgentResponse(**response_dict)
