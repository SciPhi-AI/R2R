from core.pipes.retrieval.multi_search import MultiSearchPipe
from core.pipes.retrieval.query_transform_pipe import QueryTransformPipe

from .factory import R2RPipeFactory


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
            task_prompt_name: str
            multi_query_transform_pipe_override: QueryTransformPipe
            multi_inner_search_pipe_override: SearchPipe
            query_generation_template_override: {'template': str, 'input_types': dict[str, str]}
        """
        multi_search_config = MultiSearchPipe.PipeConfig()
        if kwargs.get("task_prompt_name") and kwargs.get(
            "query_generation_template_override"
        ):
            raise ValueError(
                "Cannot provide both `task_prompt_name` and `query_generation_template_override`"
            )
        task_prompt_name = (
            kwargs.get("task_prompt_name")
            or f"{multi_search_config.name}_task_prompt"
        )
        if kwargs.get("query_generation_template_override"):
            # Add a prompt for transforming the user query
            template = kwargs.get("query_generation_template_override")
            self.providers.prompt.add_prompt(
                **(
                    kwargs.get("query_generation_template_override")
                    or self.QUERY_GENERATION_TEMPLATE
                ),
            )
            task_prompt_name = template["name"]

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
