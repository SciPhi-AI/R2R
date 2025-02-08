from typing import Any, AsyncGenerator, Optional

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


class RetrievalSDK:
    """
    SDK for interacting with documents in the v3 API.
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
        return await self.client._make_request(
            "POST",
            "retrieval/completion",
            json=data,
            version="v3",
        )

    async def embedding(
        self,
        text: str,
    ):
        # FIXME: Needs a proper return type
        data: dict[str, Any] = {
            "text": text,
        }

        return await self.client._make_request(
            "POST",
            "retrieval/embedding",
            data=data,
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
            return self.client._make_streaming_request(
                "POST",
                "retrieval/rag",
                json=data,
                version="v3",
            )

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
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        conversation_id: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tool_context_length: Optional[int] = None,
        use_system_context: Optional[bool] = True,
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
            "conversation_id": conversation_id,
            "tools": tools,
            "max_tool_context_length": max_tool_context_length,
            "use_system_context": use_system_context,
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

        response_dict = await self.client._make_request(
            "POST",
            "retrieval/agent",
            json=data,
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
            "conversation_id": conversation_id,
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
            return await self.client._make_request(
                "POST",
                "retrieval/reasoning_agent",
                json=data,
                version="v3",
            )
