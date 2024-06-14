"""A custom RAG pipeline that includes a custom query transformation prompt."""

from r2r import (
    GenerationConfig,
    KVLoggingSingleton,
    R2RConfig,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
    R2RQueryTransformPipe,
    RAGPipeline,
    run_pipeline,
)

if __name__ == "__main__":
    # Load the default configuration
    config = R2RConfig.from_json()
    KVLoggingSingleton().configure(config.logging)

    # Create input providers and pipes
    providers = R2RProviderFactory(config).create_providers()
    pipes = R2RPipeFactory(config, providers).create_pipes()

    # Add a custom prompt for transforming the user query
    transform_prompt = {
        "name": "rag_fusion_prompt_custom",
        "template": "### Instruction:\n\nGiven the following query that follows to write a double newline separated list of up to {num_outputs} queries meant to help answer the original query. \nDO NOT generate any single query which is likely to require information from multiple distinct documents, \nEACH single query will be used to carry out a cosine similarity semantic search over distinct indexed documents, such as varied medical documents. \nFOR EXAMPLE if asked `how do the key themes of Great Gatsby compare with 1984`, the two queries would be \n`What are the key themes of Great Gatsby?` and `What are the key themes of 1984?`.\nHere is the original user query to be transformed into answers:\n\n### Query:\n{message}\n\n### Response:\n",
        "input_types": {"num_outputs": "int", "message": "str"},
    }
    providers.prompt.add_prompt(**transform_prompt)

    # Initialize the new query transform pipe
    query_transform_pipe = R2RQueryTransformPipe(
        llm_provider=providers.llm,
        prompt_provider=providers.prompt,
        config=R2RQueryTransformPipe.QueryTransformConfig(
            task_prompt=transform_prompt["name"]
        ),
    )

    # Create the RAG pipeline and add the pipes
    rag_pipeline = RAGPipeline()
    rag_pipeline.add_pipe(query_transform_pipe)
    rag_pipeline.add_pipe(pipes.search_pipe)
    rag_pipeline.add_pipe(
        pipes.rag_pipe,
        add_upstream_outputs=[
            {
                "prev_pipe_name": pipes.search_pipe.config.name,
                "prev_output_field": "search_results",
                "input_field": "raw_search_results",
            },
            {
                "prev_pipe_name": pipes.search_pipe.config.name,
                "prev_output_field": "search_queries",
                "input_field": "query",
            },
        ],
    )

    # Run the pipeline
    result = run_pipeline(
        rag_pipeline,
        input="Who was aristotle?",
        num_query_xf_outputs=3,  # Number of transformed queries to generate
        query_transform_config=GenerationConfig(
            model="gpt-4o"
        ),  # LLM configuration for the query transformer
        rag_generation_config=GenerationConfig(
            model="gpt-4o"
        ),  # LLM configuration for the RAG model
    )
