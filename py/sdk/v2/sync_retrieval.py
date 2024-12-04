from __future__ import annotations  # for Python 3.10+

import logging
from typing import AsyncGenerator, Optional

from typing_extensions import deprecated

from ..models import GenerationConfig, Message, RAGResponse, SearchSettings

logger = logging.getLogger()


class SyncRetrievalMixins:
    def search_documents(
        self,
        query: str,
        search_settings: Optional[dict | SearchSettings] = None,
    ):
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.

        Returns:
            SearchResponse: The search response.
        """
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data = {
            "query": query,
            "search_settings": search_settings,
        }
        return self._make_request("POST", "search_documents", json=data)  # type: ignore

    @deprecated("Use client.retrieval.search() instead")
    def search(
        self,
        query: str,
        search_settings: Optional[dict | SearchSettings] = None,
    ):
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.

        Returns:
            CombinedSearchResponse: The search response.
        """
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data = {
            "query": query,
            "search_settings": search_settings,
        }
        return self._make_request("POST", "search", json=data)  # type: ignore

    @deprecated("Use client.retrieval.completion() instead")
    def completion(
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

        return self._make_request("POST", "completion", json=data)  # type: ignore

    @deprecated("Use client.retrieval.rag() instead")
    def rag(
        self,
        query: str,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        search_settings: Optional[dict | SearchSettings] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
    ) -> RAGResponse | AsyncGenerator[RAGResponse, None]:
        """
        Conducts a Retrieval Augmented Generation (RAG) search with the given query.

        Args:
            query (str): The query to search for.
            rag_generation_config (Optional[Union[dict, GenerationConfig]]): RAG generation configuration.
            search_settings (Optional[Union[dict, SearchSettings]]): Vector search settings.
            task_prompt_override (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            Union[RAGResponse, AsyncGenerator[RAGResponse, None]]: The RAG response
        """
        if rag_generation_config and not isinstance(
            rag_generation_config, dict
        ):
            rag_generation_config = rag_generation_config.model_dump()
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data = {
            "query": query,
            "rag_generation_config": rag_generation_config,
            "search_settings": search_settings,
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
        }

        if rag_generation_config and rag_generation_config.get(  # type: ignore
            "stream", False
        ):
            return self._make_streaming_request("POST", "rag", json=data)  # type: ignore
        else:
            return self._make_request("POST", "rag", json=data)  # type: ignore

    @deprecated("Use client.retrieval.agent() instead")
    def agent(
        self,
        message: Optional[dict | Message] = None,
        rag_generation_config: Optional[dict | GenerationConfig] = None,
        search_settings: Optional[dict | SearchSettings] = None,
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
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data = {
            "rag_generation_config": rag_generation_config or {},
            "search_settings": search_settings or {},
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
            return self._make_request("POST", "agent", json=data)  # type: ignore

    def embedding(
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
        return self._make_request("POST", "embedding", json=content)  # type: ignore
