from copy import copy, deepcopy
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from core.base.abstractions import (
    GenerationConfig,
    VectorSearchResult,
    VectorSearchSettings,
)
from core.base.pipes.base_pipe import AsyncPipe, PipeType

from ..abstractions.search_pipe import SearchPipe
from .query_transform_pipe import QueryTransformPipe


class MultiSearchPipe(AsyncPipe):
    class PipeConfig(AsyncPipe.PipeConfig):
        name: str = "multi_search_pipe"
        use_rrf: bool = False
        rrf_k: int = 60  # RRF constant
        num_queries: int = 3
        expansion_factor: int = 3  # Factor to expand results before RRF

    def __init__(
        self,
        query_transform_pipe: QueryTransformPipe,
        inner_search_pipe: SearchPipe,
        config: PipeConfig,
        *args,
        **kwargs,
    ):
        self.query_transform_pipe = query_transform_pipe
        self.vector_search_pipe = inner_search_pipe

        config = config or MultiSearchPipe.PipeConfig(
            name=query_transform_pipe.config.name
        )
        super().__init__(
            config,
            PipeType.SEARCH,
            *args,
            **kwargs,
        )
        self._config: MultiSearchPipe.PipeConfig = config  # for type hinting

    @property
    def config(self) -> PipeConfig:
        return self._config

    async def _run_logic(  # type: ignore
        self,
        input: Any,
        state: Any,
        run_id: UUID,
        vector_search_settings: VectorSearchSettings,
        query_transform_generation_config: Optional[GenerationConfig] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        query_transform_generation_config = (
            query_transform_generation_config
            or copy(kwargs.get("rag_generation_config", None))
            or GenerationConfig(model="gpt-4o")
        )
        query_transform_generation_config.stream = False

        query_generator = await self.query_transform_pipe.run(
            input,
            state,
            query_transform_generation_config=query_transform_generation_config,
            num_query_xf_outputs=self.config.num_queries,
            *args,
            **kwargs,
        )

        if self.config.use_rrf:
            vector_search_settings.search_limit = (
                self.config.expansion_factor
                * vector_search_settings.search_limit
            )
            results = []
            async for search_result in await self.vector_search_pipe.run(
                self.vector_search_pipe.Input(message=query_generator),
                state,
                vector_search_settings=vector_search_settings,
                *args,
                **kwargs,
            ):
                results.append(search_result)

            # Collection results by their associated queries
            grouped_results: dict[str, list[VectorSearchResult]] = {}
            for result in results:
                query = result.metadata["associated_query"]
                if query not in grouped_results:
                    grouped_results[query] = []
                grouped_results[query].append(result)

            fused_results = self.reciprocal_rank_fusion(grouped_results)
            for result in fused_results[: vector_search_settings.search_limit]:
                yield result
        else:
            async for search_result in await self.vector_search_pipe.run(
                self.vector_search_pipe.Input(message=query_generator),
                state,
                vector_search_settings=vector_search_settings,
                *args,
                **kwargs,
            ):
                yield search_result

    def reciprocal_rank_fusion(
        self, all_results: Dict[str, List[VectorSearchResult]]
    ) -> List[VectorSearchResult]:
        document_scores: dict[UUID, float] = {}
        document_results: dict[UUID, VectorSearchResult] = {}
        document_queries: dict[UUID, set[str]] = {}
        for query, results in all_results.items():
            for rank, result in enumerate(results, 1):
                doc_id = result.extraction_id
                if doc_id not in document_scores:
                    document_scores[doc_id] = 0
                    document_results[doc_id] = result
                    set_: set[str] = set()
                    document_queries[doc_id] = set_
                document_scores[doc_id] += 1 / (rank + self.config.rrf_k)
                document_queries[doc_id].add(query)  # type: ignore

        # Sort documents by their RRF score
        sorted_docs = sorted(
            document_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Reconstruct VectorSearchResults with new ranking, RRF score, and associated queries
        fused_results = []
        for doc_id, rrf_score in sorted_docs:
            result = deepcopy(document_results[doc_id])
            result.score = (
                rrf_score  # Replace the original score with the RRF score
            )
            result.metadata["associated_queries"] = list(
                document_queries[doc_id]  # type: ignore
            )  # Add list of associated queries
            result.metadata["is_rrf_score"] = True
            if "associated_query" in result.metadata:
                del result.metadata[
                    "associated_query"
                ]  # Remove the old single associated_query
            fused_results.append(result)

        return fused_results
