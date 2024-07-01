import uuid
from copy import copy
from typing import Any, AsyncGenerator, Optional

from r2r.base.abstractions.llm import GenerationConfig
from r2r.base.abstractions.search import VectorSearchResult
from r2r.base.pipes.base_pipe import AsyncPipe

from ..abstractions.search_pipe import SearchPipe
from .query_transform_pipe import QueryTransformPipe


class MultiSearchPipe(AsyncPipe):
    class PipeConfig(AsyncPipe.PipeConfig):
        name: str = "multi_search_pipe"

    def __init__(
        self,
        query_transform_pipe: QueryTransformPipe,
        inner_search_pipe: SearchPipe,
        config: Optional[PipeConfig] = None,
        *args,
        **kwargs,
    ):
        self.query_transform_pipe = query_transform_pipe
        self.vector_search_pipe = inner_search_pipe
        if (
            not query_transform_pipe.config.name
            == inner_search_pipe.config.name
        ):
            raise ValueError(
                "The query transform pipe and search pipe must have the same name."
            )
        if config and not config.name == query_transform_pipe.config.name:
            raise ValueError(
                "The pipe config name must match the query transform pipe name."
            )

        super().__init__(
            config=config
            or MultiSearchPipe.PipeConfig(
                name=query_transform_pipe.config.name
            ),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: Any,
        state: Any,
        run_id: uuid.UUID,
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
            num_query_xf_outputs=3,
            *args,
            **kwargs,
        )

        async for search_result in await self.vector_search_pipe.run(
            self.vector_search_pipe.Input(message=query_generator),
            state,
            *args,
            **kwargs,
        ):
            yield search_result
