import logging
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import AsyncGenerator, Optional, Union

from ..base.base_client import sync_generator_wrapper, sync_wrapper
from ..models import (
    CombinedSearchResponse,
    GenerationConfig,
    KGSearchSettings,
    Message,
    RAGResponse,
    SearchSettings,
)

logger = logging.getLogger()


class RetrievalSDK:
    """
    SDK for interacting with documents in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def search(
        self,
        query: str,
        vector_search_settings: Optional[Union[dict, SearchSettings]] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
    ) -> CombinedSearchResponse:
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            vector_search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            kg_search_settings (Optional[Union[dict, KGSearchSettings]]): KG search settings.

        Returns:
            CombinedSearchResponse: The search response.
        """
        if vector_search_settings and not isinstance(
            vector_search_settings, dict
        ):
            vector_search_settings = vector_search_settings.model_dump()
        if kg_search_settings and not isinstance(kg_search_settings, dict):
            kg_search_settings = kg_search_settings.model_dump()

        data = {
            "query": query,
            "vector_search_settings": vector_search_settings,
            "kg_search_settings": kg_search_settings,
        }
        return await self.client._make_request("POST", "retrieval/search", json=data)  # type: ignore

    async def completion(
        self,
        messages: list[Union[dict, Message]],
        generation_config: Optional[Union[dict, GenerationConfig]] = None,
    ):
        cast_messages: list[Message] = [
            Message(**msg) if isinstance(msg, dict) else msg
            for msg in messages
        ]

        if generation_config and not isinstance(generation_config, dict):
            generation_config = generation_config.model_dump()

        data = {
            "messages": [msg.model_dump() for msg in cast_messages],
            "generation_config": generation_config,
        }

        return await self.client._make_request("POST", "retrieval/completion", json=data)  # type: ignore

    async def rag(
        self,
        query: str,
        rag_generation_config: Optional[Union[dict, GenerationConfig]] = None,
        vector_search_settings: Optional[Union[dict, SearchSettings]] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
    ) -> Union[RAGResponse, AsyncGenerator[RAGResponse, None]]:
        """
        Conducts a Retrieval Augmented Generation (RAG) search with the given query.

        Args:
            query (str): The query to search for.
            rag_generation_config (Optional[Union[dict, GenerationConfig]]): RAG generation configuration.
            vector_search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            kg_search_settings (Optional[Union[dict, KGSearchSettings]]): KG search settings.
            task_prompt_override (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            Union[RAGResponse, AsyncGenerator[RAGResponse, None]]: The RAG response
        """
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if vector_search_settings and not isinstance(
            vector_search_settings, dict
        ):
            vector_search_settings = vector_search_settings.model_dump()
        if kg_search_settings and not isinstance(kg_search_settings, dict):
            kg_search_settings = kg_search_settings.model_dump()

        data = {
            "query": query,
            "rag_generation_config": rag_generation_config,
            "vector_search_settings": vector_search_settings,
            "kg_search_settings": kg_search_settings,
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
        }

        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):
            return self._make_streaming_request("POST", "retrieval/rag", json=data)  # type: ignore
        else:
            return await self.client._make_request("POST", "retrieval/rag", json=data)  # type: ignore

    async def agent(
        self,
        message: Optional[Union[dict, Message]] = None,
        rag_generation_config: Optional[Union[dict, GenerationConfig]] = None,
        vector_search_settings: Optional[Union[dict, SearchSettings]] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        conversation_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        # TODO - Deprecate messages
        messages: Optional[Union[dict, Message]] = None,
    ) -> Union[list[Message], AsyncGenerator[Message, None]]:
        """
        Performs a single turn in a conversation with a RAG agent.

        Args:
            messages (List[Union[dict, Message]]): The messages to send to the agent.
            rag_generation_config (Optional[Union[dict, GenerationConfig]]): RAG generation configuration.
            vector_search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            kg_search_settings (Optional[Union[dict, KGSearchSettings]]): KG search settings.
            task_prompt_override (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            Union[List[Message], AsyncGenerator[Message, None]]: The agent response.
        """
        if messages:
            logger.warning(
                "The `messages` argument is deprecated. Please use `message` instead."
            )
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if vector_search_settings and not isinstance(
            vector_search_settings, dict
        ):
            vector_search_settings = vector_search_settings.model_dump()
        if kg_search_settings and not isinstance(kg_search_settings, dict):
            kg_search_settings = kg_search_settings.model_dump()

        data = {
            "rag_generation_config": rag_generation_config or {},
            "vector_search_settings": vector_search_settings or {},
            "kg_search_settings": kg_search_settings,
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
            "conversation_id": conversation_id,
            "branch_id": branch_id,
        }

        if message:
            cast_message: Message = (
                Message(**message) if isinstance(message, dict) else message
            )
            data["message"] = cast_message.model_dump()

        if messages:
            data["messages"] = [
                (
                    Message(**msg).model_dump()  # type: ignore
                    if isinstance(msg, dict)
                    else msg.model_dump()  # type: ignore
                )
                for msg in messages
            ]

        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):
            return self._make_streaming_request("POST", "retrieval/agent", json=data)  # type: ignore
        else:
            return await self.client._make_request("POST", "retrieval/agent", json=data)  # type: ignore


class SyncRetrievalSDK:
    """Synchronous wrapper for ChunksSDK"""

    def __init__(self, async_sdk: RetrievalSDK):
        self._async_sdk = async_sdk

        # Get all attributes from the instance
        for name in dir(async_sdk):
            if not name.startswith("_"):  # Skip private methods
                attr = getattr(async_sdk, name)
                # Check if it's a method and if it's async
                if callable(attr) and (
                    iscoroutinefunction(attr) or isasyncgenfunction(attr)
                ):
                    if isasyncgenfunction(attr):
                        setattr(self, name, sync_generator_wrapper(attr))
                    else:
                        setattr(self, name, sync_wrapper(attr))
