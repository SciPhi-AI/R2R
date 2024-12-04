from __future__ import annotations  # for Python 3.10+

import logging
from typing import AsyncGenerator, Optional

from typing_extensions import deprecated

from ..models import (
    GenerationConfig,
    GraphSearchSettings,
    Message,
    RAGResponse,
    SearchSettings,
)

logger = logging.getLogger()


class RetrievalMixins:
    async def search_documents(
        self,
        query: str,
        settings: Optional[dict] = None,
    ):
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            chunk_search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            graph_search_settings (Optional[Union[dict, GraphSearchSettings]]): KG search settings.

        Returns:
            SearchResponse: The search response.
        """
        if settings and not isinstance(settings, dict):
            settings = settings.model_dump()

        data = {
            "query": query,
            "settings": settings,
        }
        return await self._make_request("POST", "search_documents", json=data)  # type: ignore

    @deprecated("Use client.retrieval.search() instead")
    async def search(
        self,
        query: str,
        chunk_search_settings: Optional[dict | SearchSettings] = None,
        graph_search_settings: Optional[dict | GraphSearchSettings] = None,
    ):
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            chunk_search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            graph_search_settings (Optional[Union[dict, GraphSearchSettings]]): KG search settings.

        Returns:
            CombinedSearchResponse: The search response.
        """
        if chunk_search_settings and not isinstance(
            chunk_search_settings, dict
        ):
            chunk_search_settings = chunk_search_settings.model_dump()
        if graph_search_settings and not isinstance(
            graph_search_settings, dict
        ):
            graph_search_settings = graph_search_settings.model_dump()

        data = {
            "query": query,
            "chunk_search_settings": chunk_search_settings,
            "graph_search_settings": graph_search_settings,
        }
        return await self._make_request("POST", "search", json=data)  # type: ignore

    @deprecated("Use client.retrieval.completion() instead")
    async def completion(
        self,
        messages: list[dict | Message],
        generation_config: Optional[dict | GenerationConfig] = None,
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

        return await self._make_request("POST", "completion", json=data)  # type: ignore

    @deprecated("Use client.retrieval.rag() instead")
    async def rag(
        self,
        query: str,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        chunk_search_settings: Optional[dict | SearchSettings] = None,
        graph_search_settings: Optional[dict | GraphSearchSettings] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
    ) -> RAGResponse | AsyncGenerator[RAGResponse, None]:
        """
        Conducts a Retrieval Augmented Generation (RAG) search with the given query.

        Args:
            query (str): The query to search for.
            rag_generation_config (Optional[Union[dict, GenerationConfig]]): RAG generation configuration.
            chunk_search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            graph_search_settings (Optional[Union[dict, GraphSearchSettings]]): KG search settings.
            task_prompt_override (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            Union[RAGResponse, AsyncGenerator[RAGResponse, None]]: The RAG response
        """
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if chunk_search_settings and not isinstance(
            chunk_search_settings, dict
        ):
            chunk_search_settings = chunk_search_settings.model_dump()
        if graph_search_settings and not isinstance(
            graph_search_settings, dict
        ):
            graph_search_settings = graph_search_settings.model_dump()

        data = {
            "query": query,
            "rag_generation_config": rag_generation_config,
            "chunk_search_settings": chunk_search_settings,
            "graph_search_settings": graph_search_settings,
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
        }

        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):
            return self._make_streaming_request("POST", "rag", json=data)  # type: ignore
        else:
            return await self._make_request("POST", "rag", json=data)  # type: ignore

    @deprecated("Use client.retrieval.agent() instead")
    async def agent(
        self,
        message: Optional[dict | Message] = None,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        chunk_search_settings: Optional[dict | SearchSettings] = None,
        graph_search_settings: Optional[dict | GraphSearchSettings] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        conversation_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        # TODO - Deprecate messages
        messages: Optional[dict | Message] = None,
    ) -> list[Message] | AsyncGenerator[Message, None]:
        """
        Performs a single turn in a conversation with a RAG agent.

        Args:
            messages (List[Union[dict, Message]]): The messages to send to the agent.
            rag_generation_config (Optional[Union[dict, GenerationConfig]]): RAG generation configuration.
            chunk_search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            graph_search_settings (Optional[Union[dict, GraphSearchSettings]]): KG search settings.
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
        if chunk_search_settings and not isinstance(
            chunk_search_settings, dict
        ):
            chunk_search_settings = chunk_search_settings.model_dump()
        if graph_search_settings and not isinstance(
            graph_search_settings, dict
        ):
            graph_search_settings = graph_search_settings.model_dump()

        data = {
            "rag_generation_config": rag_generation_config or {},
            "chunk_search_settings": chunk_search_settings or {},
            "graph_search_settings": graph_search_settings,
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
            return self._make_streaming_request("POST", "agent", json=data)  # type: ignore
        else:
            return await self._make_request("POST", "agent", json=data)  # type: ignore

    @deprecated("Use client.retrieval.embedding() instead")
    async def embedding(
        self,
        content: str,
    ) -> list[float]:
        """
        Generate embeddings for the provided content.

        Args:
            content (str): The text content to embed.

        Returns:
            list[float]: The generated embedding vector.
        """
        return await self._make_request("POST", "embedding", json=content)  # type: ignore
