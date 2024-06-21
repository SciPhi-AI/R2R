import uuid
from copy import copy
from typing import Any, AsyncGenerator, Optional

from r2r import (
    LoggableAsyncPipe,
    QueryTransformPipe,
    R2RPipeFactory,
    SearchPipe,
    VectorSearchResult,
)
from r2r.core.abstractions.llm import GenerationConfig


class MultiSearchPipe(LoggableAsyncPipe):
    class PipeConfig(LoggableAsyncPipe.PipeConfig):
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


class R2RPipeFactoryWithMultiSearch(R2RPipeFactory):
    QUERY_GENERATION_TEMPLATE: dict = (
        {  # TODO - Can we have stricter typing like so? `: {"template": str, "input_types": dict[str, str]} = {``
            "template": "### Instruction:\n\nGiven the following query that follows to write a double newline separated list of up to {num_outputs} queries meant to help answer the original query. \nDO NOT generate any single query which is likely to require information from multiple distinct documents, \nEACH single query will be used to carry out a cosine similarity semantic search over distinct indexed documents, such as varied medical documents. \nFOR EXAMPLE if asked `how do the key themes of Great Gatsby compare with 1984`, the two queries would be \n`What are the key themes of Great Gatsby?` and `What are the key themes of 1984?`.\nHere is the original user query to be transformed into answers:\n\n### Query:\n{message}\n\n### Response:\n",
            "input_types": {"num_outputs": "int", "message": "str"},
        }
    )

    def create_vector_search_pipe(self, *args, **kwargs):
        """
        A factory method to create a search pipe.

        Overrides include
            multi_query_transform_pipe_override: QueryTransformPipe
            multi_inner_search_pipe_override: SearchPipe
            search_task_template_override: {'template': str, 'input_types': dict[str, str]}
        """
        multi_search_config = MultiSearchPipe.PipeConfig()
        task_prompt_name = (
            kwargs.get("task_prompt_name")
            or f"{multi_search_config.name}_task_prompt"
        )

        # Initialize the new query transform pipe
        query_transform_pipe = kwargs.get(
            "multi_query_transform_pipe_override", None
        ) or QueryTransformPipe(
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            config=QueryTransformPipe.QueryTransformConfig(
                name=multi_search_config.name,
                task_prompt=task_prompt_name,
            ),
        )
        if kwargs.get("task_prompt_name") is None:
            # Add a prompt for transforming the user query
            self.providers.prompt.add_prompt(
                name=task_prompt_name,
                **(
                    kwargs.get("query_generation_template_override")
                    or self.QUERY_GENERATION_TEMPLATE
                ),
            )

        # Create search pipe override and pipes
        inner_search_pipe = kwargs.get(
            "multi_inner_search_pipe_override", None
        ) or super().create_vector_search_pipe(*args, **kwargs)

        # TODO - modify `create_..._pipe` to allow naming the pipe
        inner_search_pipe.config.name = multi_search_config.name

        return MultiSearchPipe(
            query_transform_pipe=query_transform_pipe,
            inner_search_pipe=inner_search_pipe,
            config=multi_search_config,
        )
