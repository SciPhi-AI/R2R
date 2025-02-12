import uuid
from typing import Any, AsyncGenerator, Optional, Union

# Import the same models you use in your sync version
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

# Import all the relevant shared logic from the sync module
# (the same file or package where you placed them above)
from ..sync_methods.retrieval import (
    agent_arg_parser,
    completion_arg_parser,
    embedding_arg_parser,
    parse_rag_event,
    rag_arg_parser,
    reasoning_agent_arg_parser,
    search_arg_parser,
)


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
        """
        payload = search_arg_parser(
            query=query,
            search_mode=search_mode,
            search_settings=search_settings,
        )
        response_dict = await self.client._make_request(
            "POST",
            "retrieval/search",
            json=payload,
            version="v3",
        )
        return WrappedSearchResponse(**response_dict)

    async def completion(
        self,
        messages: list[dict | Message],
        generation_config: Optional[dict | GenerationConfig] = None,
    ):
        """
        Get a completion from the model (async).
        """
        payload = completion_arg_parser(messages, generation_config)
        return await self.client._make_request(
            "POST",
            "retrieval/completion",
            json=payload,
            version="v3",
        )

    async def embedding(
        self,
        text: str,
    ):
        """
        Generate an embedding for given text (async).
        """
        payload = embedding_arg_parser(text)
        return await self.client._make_request(
            "POST",
            "retrieval/embedding",
            data=payload,  # or json=payload if your server expects JSON
            version="v3",
        )

    async def rag(
        self,
        query: str,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
    ) -> WrappedRAGResponse | AsyncGenerator[RAGResponse, None]:
        """
        Conducts a Retrieval Augmented Generation (RAG) search (async).
        May return a `WrappedRAGResponse` or a streaming generator if `stream=True`.
        """
        payload = rag_arg_parser(
            query=query,
            rag_generation_config=rag_generation_config,
            search_mode=search_mode,
            search_settings=search_settings,
            task_prompt_override=task_prompt_override,
            include_title_if_available=include_title_if_available,
        )

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            # Return an async streaming generator
            raw_stream = self.client._make_streaming_request(
                "POST",
                "retrieval/rag",
                json=payload,
                version="v3",
            )
            # Wrap each raw SSE event with parse_rag_event
            return (parse_rag_event(event) for event in raw_stream)

        # Otherwise, request fully and parse response
        response_dict = await self.client._make_request(
            "POST",
            "retrieval/rag",
            json=payload,
            version="v3",
        )
        return WrappedRAGResponse(**response_dict)

    async def agent(
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
        Performs a single turn in a conversation with a RAG agent (async).
        May return a `WrappedAgentResponse` or a streaming generator if `stream=True`.
        """
        payload = agent_arg_parser(
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

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            # Return an async streaming generator
            return self.client._make_streaming_request(
                "POST",
                "retrieval/agent",
                json=payload,
                version="v3",
            )

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/agent",
            json=payload,
            version="v3",
        )
        return WrappedAgentResponse(**response_dict)

    async def reasoning_agent(
        self,
        message: Optional[dict | Message] = None,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        conversation_id: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tool_context_length: Optional[int] = None,
    ) -> WrappedAgentResponse | AsyncGenerator[Message, None]:
        """
        Performs a single turn in a conversation with a RAG agent in Reasoning mode (async).
        May return a `WrappedAgentResponse` or a streaming generator if `stream=True`.
        """
        payload = reasoning_agent_arg_parser(
            message=message,
            rag_generation_config=rag_generation_config,
            conversation_id=conversation_id,
            tools=tools,
            max_tool_context_length=max_tool_context_length,
        )

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            # Return an async streaming generator
            return self.client._make_streaming_request(
                "POST",
                "retrieval/reasoning_agent",
                json=payload,
                version="v3",
            )
        else:
            return await self.client._make_request(
                "POST",
                "retrieval/reasoning_agent",
                json=payload,
                version="v3",
            )
