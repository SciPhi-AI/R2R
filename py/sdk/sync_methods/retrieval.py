import json
import uuid
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Union

from pydantic import BaseModel

from shared.api.models import (
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


# A generic base model for SSE events
class SSEEventBase(BaseModel):
    event: str
    data: Dict[str, Any]


# Model for the search results event
class SearchResultsData(BaseModel):
    id: str
    object: str
    data: Dict[
        str, Any
    ]  # You can replace Dict[str, Any] with a more specific type if available


class SearchResultsEvent(SSEEventBase):
    event: Literal["search_results"]
    data: SearchResultsData


# Model for message events (partial tokens)
class MessageDelta(BaseModel):
    type: str
    text: Dict[str, Any]  # Adjust if you have a more specific structure


class MessageData(BaseModel):
    id: str
    object: str
    delta: Dict[str, List[MessageDelta]]  # This reflects your nested structure


class MessageEvent(SSEEventBase):
    event: Literal["message"]
    data: MessageData


# Model for citation events
class CitationData(BaseModel):
    rawIndex: int


class CitationEvent(SSEEventBase):
    event: Literal["citation"]
    data: CitationData


# Model for the final answer event
class FinalAnswerData(BaseModel):
    generated_answer: str
    citations: List[Dict[str, Any]]  # refine if you have a citation model


class FinalAnswerEvent(SSEEventBase):
    event: Literal["final_answer"]
    data: FinalAnswerData


# Optionally, define a fallback model for unrecognized events
class UnknownEvent(SSEEventBase):
    pass


# Create a union type for all RAG events
RAGEvent = Union[
    SearchResultsEvent,
    MessageEvent,
    CitationEvent,
    FinalAnswerEvent,
    UnknownEvent,
]


def parse_rag_event(raw: dict):
    """
    raw is something like:
      {
        "event": "search_results",
        "data": "{\"id\":\"run_1\",\"object\":\"rag.search_results\", \"data\":{...}}"
      }
    """
    event_type = raw.get("event", "unknown")
    # Then branch on event_type:
    if event_type == "done":
        return None

    # The SSE data is a JSON string, so parse it:
    data_str = raw.get("data", "")
    try:
        data_obj = json.loads(data_str)  # Now we have a dict
    except json.JSONDecodeError as e:
        print("JSON parse error:", e)
        print("Raw string was:", repr(data_str))
        # Raise or return something
        raise

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
        return CitationEvent(
            event=event_type,
            data=CitationData(**data_obj),
        )
    elif event_type == "final_answer":
        print("final answer data obj = ", data_obj)
        return FinalAnswerEvent(
            event=event_type,
            data=FinalAnswerData(**data_obj["data"]),
        )
    else:
        return UnknownEvent(
            event=event_type,
            data=data_obj,
        )


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
    ):
        # FIXME: Needs a proper return type
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
        return self.client._make_request(
            "POST",
            "retrieval/completion",
            json=data,
            version="v3",
        )

    def embedding(
        self,
        text: str,
    ):
        # FIXME: Needs a proper return type
        data: dict[str, Any] = {
            "text": text,
        }

        return self.client._make_request(
            "POST",
            "retrieval/embedding",
            data=data,
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
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
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
            return (parse_rag_event(event) for event in raw_stream)

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
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data: dict[str, Any] = {
            "rag_generation_config": rag_generation_config or {},
            "search_settings": search_settings,
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
            "conversation_id": (
                str(conversation_id) if conversation_id else None
            ),
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
        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):
            return self.client._make_streaming_request(
                "POST",
                "retrieval/agent",
                json=data,
                version="v3",
            )

        response_dict = self.client._make_request(
            "POST",
            "retrieval/agent",
            json=data,
            version="v3",
        )

        return WrappedAgentResponse(**response_dict)

    def reasoning_agent(
        self,
        message: Optional[dict | Message] = None,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        conversation_id: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tool_context_length: Optional[int] = None,
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
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()

        data: dict[str, Any] = {
            "rag_generation_config": rag_generation_config or {},
            "conversation_id": (
                str(conversation_id) if conversation_id else None
            ),
            "tools": tools,
            "max_tool_context_length": max_tool_context_length,
        }

        if message:
            cast_message: Message = (
                Message(**message) if isinstance(message, dict) else message
            )
            data["message"] = cast_message.model_dump()
        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):
            return self.client._make_streaming_request(
                "POST",
                "retrieval/reasoning_agent",
                json=data,
                version="v3",
            )
        else:
            return self.client._make_request(
                "POST",
                "retrieval/reasoning_agent",
                json=data,
                version="v3",
            )
