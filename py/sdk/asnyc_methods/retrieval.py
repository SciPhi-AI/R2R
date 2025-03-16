from typing import Generator

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
    WrappedRAGResponse,
    WrappedSearchResponse,
)

from ..models import (
    Message,
)
from ..sync_methods.retrieval import parse_retrieval_event


class RetrievalSDK:
    """
    SDK for interacting with documents in the v3 API (Asynchronous).
    """

    def __init__(self, client):
        self.client = client

    async def search(self, **kwargs) -> WrappedSearchResponse:
        """
        Conduct a vector and/or graph search (async).

        Args:
            query (str): Search query to find relevant documents.
            search_mode (Optional[str | SearchMode]): Pre-configured search modes: "basic", "advanced", or "custom".
            search_settings (Optional[dict | SearchSettings]): The search configuration object. If search_mode is "custom",
                these settings are used as-is. For "basic" or "advanced", these settings
                will override the default mode configuration.

        Returns:
            WrappedSearchResponse: The search results.
        """
        # Extract the required query parameter
        query = kwargs.pop("query", None)
        if query is None:
            raise ValueError("'query' is a required parameter for search")

        # Process common parameters
        search_mode = kwargs.pop("search_mode", "custom")
        search_settings = kwargs.pop("search_settings", None)

        # Handle type conversions
        if search_mode and not isinstance(search_mode, str):
            search_mode = search_mode.value
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        # Build payload
        payload = {
            "query": query,
            "search_mode": search_mode,
            "search_settings": search_settings,
            **kwargs,  # Include any additional parameters
        }

        # Filter out None values
        payload = {k: v for k, v in payload.items() if v is not None}

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/search",
            json=payload,
            version="v3",
        )
        return WrappedSearchResponse(**response_dict)

    async def completion(self, **kwargs):
        """
        Get a completion from the model (async).

        Args:
            messages (list[dict | Message]): List of messages to generate completion for. Each message
                should have a 'role' and 'content'.
            generation_config (Optional[dict | GenerationConfig]): Configuration for text generation.

        Returns:
            The completion response.
        """
        # Extract required parameters
        messages = kwargs.pop("messages", None)
        if messages is None:
            raise ValueError(
                "'messages' is a required parameter for completion"
            )

        # Process optional parameters
        generation_config = kwargs.pop("generation_config", None)

        # Handle type conversions
        cast_messages = [
            Message(**msg) if isinstance(msg, dict) else msg
            for msg in messages
        ]
        if generation_config and not isinstance(generation_config, dict):
            generation_config = generation_config.model_dump()

        # Build payload
        payload = {
            "messages": [msg.model_dump() for msg in cast_messages],
            "generation_config": generation_config,
            **kwargs,  # Include any additional parameters
        }

        # Filter out None values
        payload = {k: v for k, v in payload.items() if v is not None}

        return await self.client._make_request(
            "POST",
            "retrieval/completion",
            json=payload,
            version="v3",
        )

    async def embedding(self, **kwargs):
        """
        Generate an embedding for given text (async).

        Args:
            text (str): Text to generate embeddings for.

        Returns:
            The embedding vector.
        """
        # Extract required parameters
        text = kwargs.pop("text", None)
        if text is None:
            raise ValueError("'text' is a required parameter for embedding")

        # Build payload
        payload = {"text": text, **kwargs}  # Include any additional parameters

        return await self.client._make_request(
            "POST",
            "retrieval/embedding",
            data=payload,
            version="v3",
        )

    async def rag(
        self, **kwargs
    ) -> (
        WrappedRAGResponse
        | Generator[
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
            None,
        ]
    ):
        """
        Conducts a Retrieval Augmented Generation (RAG) search (async).
        May return a `WrappedRAGResponse` or a streaming generator if `stream=True`.

        Args:
            query (str): The search query.
            rag_generation_config (Optional[dict | GenerationConfig]): Configuration for RAG generation.
            search_mode (Optional[str | SearchMode]): Pre-configured search modes: "basic", "advanced", or "custom".
            search_settings (Optional[dict | SearchSettings]): The search configuration object.
            task_prompt (Optional[str]): Optional custom prompt to override default.
            include_title_if_available (Optional[bool]): Include document titles in responses when available.
            include_web_search (Optional[bool]): Include web search results provided to the LLM.

        Returns:
            Either a WrappedRAGResponse or an AsyncGenerator for streaming.
        """
        # Extract required parameters
        query = kwargs.pop("query", None)
        if query is None:
            raise ValueError("'query' is a required parameter for rag")

        # Process optional parameters
        rag_generation_config = kwargs.pop("rag_generation_config", None)
        search_mode = kwargs.pop("search_mode", "custom")
        search_settings = kwargs.pop("search_settings", None)
        task_prompt = kwargs.pop("task_prompt", None)
        include_title_if_available = kwargs.pop(
            "include_title_if_available", False
        )
        include_web_search = kwargs.pop("include_web_search", False)

        # Handle type conversions
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if search_mode and not isinstance(search_mode, str):
            search_mode = search_mode.value
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        # Build payload
        payload = {
            "query": query,
            "rag_generation_config": rag_generation_config,
            "search_mode": search_mode,
            "search_settings": search_settings,
            "task_prompt": task_prompt,
            "include_title_if_available": include_title_if_available,
            "include_web_search": include_web_search,
            **kwargs,  # Include any additional parameters
        }

        # Filter out None values
        payload = {k: v for k, v in payload.items() if v is not None}

        # Check if streaming is enabled
        is_stream = False
        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            is_stream = True

        if is_stream:
            # Return an async streaming generator
            raw_stream = self.client._make_streaming_request(
                "POST",
                "retrieval/rag",
                json=payload,
                version="v3",
            )
            # Wrap each raw SSE event with parse_rag_event
            return (parse_retrieval_event(event) for event in raw_stream)

        # Otherwise, request fully and parse response
        response_dict = await self.client._make_request(
            "POST",
            "retrieval/rag",
            json=payload,
            version="v3",
        )
        return WrappedRAGResponse(**response_dict)

    async def agent(
        self, **kwargs
    ) -> (
        WrappedAgentResponse
        | Generator[
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
            conversation_id (Optional[str | uuid.UUID]): ID of the conversation.
            tools (Optional[list[str]]): List of tools to execute (deprecated).
            rag_tools (Optional[list[str]]): List of tools to enable for RAG mode.
            research_tools (Optional[list[str]]): List of tools to enable for Research mode.
            max_tool_context_length (Optional[int]): Maximum length of returned tool context.
            use_system_context (Optional[bool]): Use extended prompt for generation.
            mode (Optional[Literal["rag", "research"]]): Mode to use for generation: 'rag' or 'research'.

        Returns:
            Either a WrappedAgentResponse or an AsyncGenerator for streaming.
        """
        # Extract parameters
        message = kwargs.pop("message", None)
        messages = kwargs.pop("messages", None)  # Deprecated
        rag_generation_config = kwargs.pop("rag_generation_config", None)
        research_generation_config = kwargs.pop(
            "research_generation_config", None
        )
        search_mode = kwargs.pop("search_mode", "custom")
        search_settings = kwargs.pop("search_settings", None)
        task_prompt = kwargs.pop("task_prompt", None)
        include_title_if_available = kwargs.pop(
            "include_title_if_available", True
        )
        conversation_id = kwargs.pop("conversation_id", None)
        tools = kwargs.pop("tools", None)  # Deprecated
        rag_tools = kwargs.pop("rag_tools", None)
        research_tools = kwargs.pop("research_tools", None)
        max_tool_context_length = kwargs.pop("max_tool_context_length", 32768)
        use_system_context = kwargs.pop("use_system_context", True)
        mode = kwargs.pop("mode", "rag")

        # Handle type conversions
        if message and isinstance(message, dict):
            message = Message(**message).model_dump()
        elif message:
            message = message.model_dump()

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

        if search_mode and not isinstance(search_mode, str):
            search_mode = search_mode.value

        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        # Build payload
        payload = {
            "message": message,
            "messages": messages,  # Deprecated but included for backward compatibility
            "rag_generation_config": rag_generation_config,
            "research_generation_config": research_generation_config,
            "search_mode": search_mode,
            "search_settings": search_settings,
            "task_prompt": task_prompt,
            "include_title_if_available": include_title_if_available,
            "conversation_id": (
                str(conversation_id) if conversation_id else None
            ),
            "tools": tools,  # Deprecated but included for backward compatibility
            "rag_tools": rag_tools,
            "research_tools": research_tools,
            "max_tool_context_length": max_tool_context_length,
            "use_system_context": use_system_context,
            "mode": mode,
            **kwargs,  # Include any additional parameters
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        # Check if streaming is enabled
        is_stream = False
        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            is_stream = True
        elif (
            research_generation_config
            and mode == "research"
            and research_generation_config.get("stream", False)
        ):
            is_stream = True

        if is_stream:
            # Return an async streaming generator
            raw_stream = self.client._make_streaming_request(
                "POST",
                "retrieval/agent",
                json=payload,
                version="v3",
            )
            # Parse each event in the stream
            return (parse_retrieval_event(event) for event in raw_stream)

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/agent",
            json=payload,
            version="v3",
        )
        return WrappedAgentResponse(**response_dict)
