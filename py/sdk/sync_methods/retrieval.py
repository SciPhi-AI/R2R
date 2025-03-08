import json
import uuid
from typing import Any, AsyncGenerator, Optional, Union

from core.base.api.models import (
    AgentEvent,
    CitationData,
    CitationEvent,
    FinalAnswerData,
    FinalAnswerEvent,
    MessageData,
    MessageEvent,
    SearchResultsData,
    SearchResultsEvent,
    ThinkingData,
    ThinkingEvent,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
    UnknownEvent,
    WrappedAgentResponse,
    WrappedRAGResponse,
    WrappedSearchResponse,
)

from ..models import (
    GenerationConfig,
    Message,
    RAGResponse,
    SearchMode,
    SearchSettings,
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
        raise ValueError(f"Could not parse JSON in SSE event data: {e}")

    # Now branch on event_type to build the right Pydantic model
    if event_type == "search_results":
        return SearchResultsEvent(
            event=event_type,
            data=SearchResultsData(**data_obj),
        )
    elif event_type == "message":
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
        return ThinkingEvent(
            event=event_type,
            data=ThinkingData(**data_obj),
        )
    elif event_type == "final_answer":
        print("data_obj = ", data_obj)
        return FinalAnswerEvent(
            event=event_type, data=FinalAnswerData(**data_obj)
        )
    else:
        # Fallback if it doesn't match any known event
        return UnknownEvent(
            event=event_type,
            data=data_obj,
        )


def search_arg_parser(
    query: str,
    search_mode: Optional[str | SearchMode] = "custom",
    search_settings: Optional[dict | SearchSettings] = None,
) -> dict:
    if search_mode and not isinstance(search_mode, str):
        search_mode = search_mode.value

    if search_settings and not isinstance(search_settings, dict):
        search_settings = search_settings.model_dump()

    data: dict[str, Any] = {
        "query": query,
        "search_settings": search_settings,
    }
    if search_mode:
        data["search_mode"] = search_mode

    return data


def completion_arg_parser(
    messages: list[dict | Message],
    generation_config: Optional[dict | GenerationConfig] = None,
) -> dict:
    # FIXME: Needs a proper return type
    cast_messages: list[Message] = [
        Message(**msg) if isinstance(msg, dict) else msg for msg in messages
    ]

    if generation_config and not isinstance(generation_config, dict):
        generation_config = generation_config.model_dump()

    data: dict[str, Any] = {
        "messages": [msg.model_dump() for msg in cast_messages],
        "generation_config": generation_config,
    }
    return data


def embedding_arg_parser(
    text: str,
) -> dict:
    data: dict[str, Any] = {
        "text": text,
    }
    return data


def rag_arg_parser(
    query: str,
    rag_generation_config: Optional[dict | GenerationConfig] = None,
    search_mode: Optional[str | SearchMode] = "custom",
    search_settings: Optional[dict | SearchSettings] = None,
    task_prompt_override: Optional[str] = None,
    include_title_if_available: Optional[bool] = False,
) -> dict:
    if rag_generation_config and not isinstance(rag_generation_config, dict):
        rag_generation_config = rag_generation_config.model_dump()
    if search_settings and not isinstance(search_settings, dict):
        search_settings = search_settings.model_dump()

    data: dict[str, Any] = {
        "query": query,
        "rag_generation_config": rag_generation_config,
        "search_settings": search_settings,
        "task_prompt_override": task_prompt_override,
        "include_title_if_available": include_title_if_available,
    }
    if search_mode:
        data["search_mode"] = search_mode
    return data


def agent_arg_parser(
    message: Optional[dict | Message] = None,
    rag_generation_config: Optional[dict | GenerationConfig] = None,
    search_mode: Optional[str | SearchMode] = "custom",
    search_settings: Optional[dict | SearchSettings] = None,
    task_prompt_override: Optional[str] = None,
    include_title_if_available: Optional[bool] = False,
    conversation_id: Optional[Union[str, uuid.UUID]] = None,
    tools: Optional[list[dict]] = None,
    max_tool_context_length: Optional[int] = None,
    use_extended_prompt: Optional[bool] = True,
) -> dict:
    if rag_generation_config and not isinstance(rag_generation_config, dict):
        rag_generation_config = rag_generation_config.model_dump()
    if search_settings and not isinstance(search_settings, dict):
        search_settings = search_settings.model_dump()

    data: dict[str, Any] = {
        "rag_generation_config": rag_generation_config or {},
        "search_settings": search_settings,
        "task_prompt_override": task_prompt_override,
        "include_title_if_available": include_title_if_available,
        "conversation_id": (str(conversation_id) if conversation_id else None),
        "tools": tools,
        "max_tool_context_length": max_tool_context_length,
        "use_extended_prompt": use_extended_prompt,
    }
    if search_mode:
        data["search_mode"] = search_mode

    if message:
        cast_message: Message = (
            Message(**message) if isinstance(message, dict) else message
        )
        data["message"] = cast_message.model_dump()
    return data


class RetrievalSDK:
    """
    SDK for interacting with documents in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    def search(
        self,
        query: str,
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
    ) -> WrappedSearchResponse:
        """
        Conduct a vector and/or graph search.

        Args:
            query (str): The query to search for.
            search_settings (Optional[dict, SearchSettings]]): Vector search settings.

        Returns:
            WrappedSearchResponse
        """

        response_dict = self.client._make_request(
            "POST",
            "retrieval/search",
            json=search_arg_parser(
                query=query,
                search_mode=search_mode,
                search_settings=search_settings,
            ),
            version="v3",
        )

        return WrappedSearchResponse(**response_dict)

    def completion(
        self,
        messages: list[dict | Message],
        generation_config: Optional[dict | GenerationConfig] = None,
    ):
        return self.client._make_request(
            "POST",
            "retrieval/completion",
            json=completion_arg_parser(messages, generation_config),
            version="v3",
        )

    def embedding(
        self,
        text: str,
    ):
        return self.client._make_request(
            "POST",
            "retrieval/embedding",
            data=embedding_arg_parser(text),
            version="v3",
        )

    def rag(
        self,
        query: str,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
    ) -> WrappedRAGResponse | AsyncGenerator[RAGResponse, None]:
        """
        Conducts a Retrieval Augmented Generation (RAG) search with the given query.

        Args:
            query (str): The query to search for.
            rag_generation_config (Optional[dict | GenerationConfig]): RAG generation configuration.
            search_settings (Optional[dict | SearchSettings]): Vector search settings.
            task_prompt_override (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            WrappedRAGResponse | AsyncGenerator[RAGResponse, None]: The RAG response
        """
        data = rag_arg_parser(
            query=query,
            rag_generation_config=rag_generation_config,
            search_mode=search_mode,
            search_settings=search_settings,
            task_prompt_override=task_prompt_override,
            include_title_if_available=include_title_if_available,
        )
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
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        conversation_id: Optional[Union[str, uuid.UUID]] = None,
        tools: Optional[list[dict]] = None,
        max_tool_context_length: Optional[int] = None,
        use_extended_prompt: Optional[bool] = True,
    ) -> WrappedAgentResponse | AsyncGenerator[Message, None]:
        """
        Performs a single turn in a conversation with a RAG agent.

        Args:
            message (Optional[dict | Message]): The message to send to the agent.
            search_settings (Optional[dict | SearchSettings]): Vector search settings.
            task_prompt_override (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            WrappedAgentResponse, AsyncGenerator[Message, None]]: The agent response.
        """
        data = agent_arg_parser(
            message=message,
            rag_generation_config=rag_generation_config,
            search_mode=search_mode,
            search_settings=search_settings,
            task_prompt_override=task_prompt_override,
            include_title_if_available=include_title_if_available,
            conversation_id=conversation_id,
            tools=tools,
            max_tool_context_length=max_tool_context_length,
            use_extended_prompt=use_extended_prompt,
        )
        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):
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
