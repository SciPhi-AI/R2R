from typing import AsyncGenerator, Optional, Union

from .models import (
    GenerationConfig,
    KGSearchSettings,
    Message,
    RAGResponse,
    SearchResponse,
    VectorSearchSettings,
)


class RetrievalMethods:
    @staticmethod
    async def search(
        client,
        query: str,
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
    ) -> SearchResponse:
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            vector_search_settings (Optional[Union[dict, VectorSearchSettings]]): Vector search settings.
            kg_search_settings (Optional[Union[dict, KGSearchSettings]]): KG search settings.

        Returns:
            SearchResponse: The search response.
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
        return await client._make_request("POST", "search", json=data)

    @staticmethod
    async def rag(
        client,
        query: str,
        rag_generation_config: Optional[Union[dict, GenerationConfig]] = None,
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
    ) -> Union[RAGResponse, AsyncGenerator[RAGResponse, None]]:
        """
        Conducts a Retrieval Augmented Generation (RAG) search with the given query.

        Args:
            query (str): The query to search for.
            rag_generation_config (Optional[Union[dict, GenerationConfig]]): RAG generation configuration.
            vector_search_settings (Optional[Union[dict, VectorSearchSettings]]): Vector search settings.
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

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            return client._make_streaming_request("POST", "rag", json=data)
        else:
            return await client._make_request("POST", "rag", json=data)

    @staticmethod
    async def agent(
        client,
        messages: list[Union[dict, Message]],
        rag_generation_config: Optional[Union[dict, GenerationConfig]],
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
    ) -> Union[list[Message], AsyncGenerator[Message, None]]:
        """
        Performs a single turn in a conversation with a RAG agent.

        Args:
            messages (List[Union[dict, Message]]): The messages to send to the agent.
            rag_generation_config (Optional[Union[dict, GenerationConfig]]): RAG generation configuration.
            vector_search_settings (Optional[Union[dict, VectorSearchSettings]]): Vector search settings.
            kg_search_settings (Optional[Union[dict, KGSearchSettings]]): KG search settings.
            task_prompt_override (Optional[str]): Task prompt override.
            include_title_if_available (Optional[bool]): Include the title if available.

        Returns:
            Union[List[Message], AsyncGenerator[Message, None]]: The agent response.
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

        messages = [
            Message(**msg) if isinstance(msg, dict) else msg
            for msg in messages
        ]

        data = {
            "messages": [msg.model_dump() for msg in messages],
            "rag_generation_config": rag_generation_config,
            "vector_search_settings": vector_search_settings,
            "kg_search_settings": kg_search_settings,
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
        }

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            return client._make_streaming_request("POST", "agent", json=data)
        else:
            return await client._make_request("POST", "agent", json=data)
