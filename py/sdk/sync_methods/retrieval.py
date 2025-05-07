import json
from typing import Any, Generator, Optional
from uuid import UUID

from shared.api.models import (
    WrappedAgentResponse,
    WrappedEmbeddingResponse,
    WrappedLLMChatCompletion,
    WrappedRAGResponse,
    WrappedSearchResponse,
)

from ..models import (
    AgentEvent,
    CitationData,
    CitationEvent,
    Delta,
    DeltaPayload,
    FinalAnswerData,
    FinalAnswerEvent,
    GenerationConfig,
    Message,
    MessageData,
    MessageDelta,
    MessageEvent,
    SearchMode,
    SearchResultsData,
    SearchResultsEvent,
    SearchSettings,
    ThinkingData,
    ThinkingEvent,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
    UnknownEvent,
)


def parse_retrieval_event(raw: dict) -> Optional[AgentEvent]:
    """
    Convert a raw SSE event dict into a typed Pydantic model.

    Example raw dict:
        {
          "event": "message",
          "data": "{\"id\": \"msg_partial\", \"object\": \"agent.message.delta\", \"delta\": {...}}"
        }
    """
    event_type = raw.get("event", "unknown")

    # If event_type == "done", we usually return None to signal the SSE stream is finished.
    if event_type == "done":
        return None

    # The SSE "data" is JSON-encoded, so parse it
    data_str = raw.get("data", "")
    try:
        data_obj = json.loads(data_str)
    except json.JSONDecodeError as e:
        # You can decide whether to raise or return UnknownEvent
        raise ValueError(f"Could not parse JSON in SSE event data: {e}") from e

    # Now branch on event_type to build the right Pydantic model
    if event_type == "search_results":
        return SearchResultsEvent(
            event=event_type,
            data=SearchResultsData(**data_obj),
        )
    elif event_type == "message":
        # Parse nested delta structure manually before creating MessageData
        if "delta" in data_obj and isinstance(data_obj["delta"], dict):
            delta_dict = data_obj["delta"]

            # Convert content items to MessageDelta objects
            if "content" in delta_dict and isinstance(
                delta_dict["content"], list
            ):
                parsed_content = []
                for item in delta_dict["content"]:
                    if isinstance(item, dict):
                        # Parse payload to DeltaPayload
                        if "payload" in item and isinstance(
                            item["payload"], dict
                        ):
                            payload_dict = item["payload"]
                            item["payload"] = DeltaPayload(**payload_dict)
                        parsed_content.append(MessageDelta(**item))

                # Replace with parsed content
                delta_dict["content"] = parsed_content

            # Create properly typed Delta object
            data_obj["delta"] = Delta(**delta_dict)

        return MessageEvent(
            event=event_type,
            data=MessageData(**data_obj),
        )
    elif event_type == "citation":
        return CitationEvent(event=event_type, data=CitationData(**data_obj))
    elif event_type == "tool_call":
        return ToolCallEvent(event=event_type, data=ToolCallData(**data_obj))
    elif event_type == "tool_result":
        return ToolResultEvent(
            event=event_type, data=ToolResultData(**data_obj)
        )
    elif event_type == "thinking":
        # Parse nested delta structure manually before creating ThinkingData
        if "delta" in data_obj and isinstance(data_obj["delta"], dict):
            delta_dict = data_obj["delta"]

            # Convert content items to MessageDelta objects
            if "content" in delta_dict and isinstance(
                delta_dict["content"], list
            ):
                parsed_content = []
                for item in delta_dict["content"]:
                    if isinstance(item, dict):
                        # Parse payload to DeltaPayload
                        if "payload" in item and isinstance(
                            item["payload"], dict
                        ):
                            payload_dict = item["payload"]
                            item["payload"] = DeltaPayload(**payload_dict)
                        parsed_content.append(MessageDelta(**item))

                # Replace with parsed content
                delta_dict["content"] = parsed_content

            # Create properly typed Delta object
            data_obj["delta"] = Delta(**delta_dict)

        return ThinkingEvent(
            event=event_type,
            data=ThinkingData(**data_obj),
        )
    elif event_type == "final_answer":
        return FinalAnswerEvent(
            event=event_type, data=FinalAnswerData(**data_obj)
        )
    else:
        # Fallback if it doesn't match any known event
        return UnknownEvent(
            event=event_type,
            data=data_obj,
        )


class RetrievalSDK:
    """SDK for interacting with documents in the v3 API."""

    def __init__(self, client):
        self.client = client

    def search(
        self,
        query: str,
        search_mode: Optional[str | SearchMode] = SearchMode.custom,
        search_settings: Optional[dict | SearchSettings] = None,
    ) -> WrappedSearchResponse:
        """Conduct a vector and/or graph search.

        Args:
            query (str): The search query.
            search_mode (Optional[str | SearchMode]): Search mode ('basic', 'advanced', 'custom'). Defaults to 'custom'.
            search_settings (Optional[dict | SearchSettings]): Search settings (filters, limits, hybrid options, etc.).

        Returns:
            WrappedSearchResponse
        """
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data: dict[str, Any] = {
            "query": query,
            "search_settings": search_settings,
        }
        if search_mode:
            data["search_mode"] = search_mode

        response_dict = self.client._make_request(
            "POST",
            "retrieval/search",
            json=data,
            version="v3",
        )

        return WrappedSearchResponse(**response_dict)

    def completion(
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

        response_dict = self.client._make_request(
            "POST",
            "retrieval/completion",
            json=data,
            version="v3",
        )

        return WrappedLLMChatCompletion(**response_dict)

    def embedding(self, text: str) -> WrappedEmbeddingResponse:
        """Generate an embedding for given text.

        Args:
            text (str): Text to generate embeddings for.

        Returns:
            WrappedEmbeddingResponse
        """
        data: dict[str, Any] = {
            "text": text,
        }

        response_dict = self.client._make_request(
            "POST",
            "retrieval/embedding",
            data=data,
            version="v3",
        )

        return WrappedEmbeddingResponse(**response_dict)

    def rag(
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
            raw_stream = self.client._make_streaming_request(
                "POST",
                "retrieval/rag",
                json=data,
                version="v3",
            )
            # Wrap the raw stream to parse each event
            return (parse_retrieval_event(event) for event in raw_stream)

        response_dict = self.client._make_request(
            "POST",
            "retrieval/rag",
            json=data,
            version="v3",
        )

        return WrappedRAGResponse(**response_dict)

    def agent(
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
        """Performs a single turn in a conversation with a RAG agent.

        Args:
            message (Optional[dict | Message]): The message to send to the agent.
            rag_generation_config (Optional[dict | GenerationConfig]): Configuration for RAG generation in 'rag' mode.
            research_generation_config (Optional[dict | GenerationConfig]): Configuration for generation in 'research' mode.
            search_mode (Optional[str | SearchMode]): Pre-configured search modes: "basic", "advanced", or "custom".
            search_settings (Optional[dict | SearchSettings]): Vector search settings.
            task_prompt (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.
            conversation_id (Optional[str | UUID]): ID of the conversation for maintaining context.
            max_tool_context_length (Optional[int]): Maximum context length for tool replies.
            use_system_context (Optional[bool]): Whether to use system context in the prompt.
            rag_tools (Optional[list[str]]): List of tools to enable for RAG mode.
                Available tools: "search_file_knowledge", "content", "web_search", "web_scrape", "search_file_descriptions".
            research_tools (Optional[list[str]]): List of tools to enable for Research mode.
                Available tools: "rag", "reasoning", "critique", "python_executor".
            tools (Optional[list[str]]): Deprecated. List of tools to execute.
            mode (Optional[str]): Mode to use for generation: "rag" for standard retrieval or "research" for deep analysis.
                Defaults to "rag".

        Returns:
            WrappedAgentResponse | AsyncGenerator[AgentEvent, None]: The agent response.
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
            raw_stream = self.client._make_streaming_request(
                "POST",
                "retrieval/agent",
                json=data,
                version="v3",
            )
            return (parse_retrieval_event(event) for event in raw_stream)

        response_dict = self.client._make_request(
            "POST",
            "retrieval/agent",
            json=data,
            version="v3",
        )

        return WrappedAgentResponse(**response_dict)
