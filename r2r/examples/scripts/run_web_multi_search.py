from r2r import (
    GenerationConfig,
    R2RAppBuilder,
    R2RConfig,
    R2RWebSearchPipe,
    SerperClient,
    MultiSearchPipe,
    R2RPipeFactoryWithMultiSearch,
)

if __name__ == "__main__":
    # Load the configuration file
    config = R2RConfig.from_json()

    multi_search_config = MultiSearchPipe.PipeConfig()

    # Override default inner search pipe (vector store search) with web search
    web_search_pipe = R2RWebSearchPipe(
        serper_client=SerperClient(),  # TODO - Develop a `WebSearchProvider` for configurability
    )

    synthetic_query_generation_template = {
        "template": "### Instruction:\n\nGiven the following query that follows to write a double newline separated list of up to {num_outputs} advanced queries meant to help answer the original query. \nDO NOT generate any single query which is likely to require information from multiple distinct documents, \nEACH single query will be used to carry out a cosine similarity semantic search over distinct indexed documents, such as varied medical documents. \nFOR EXAMPLE if asked `how do the key themes of Great Gatsby compare with 1984`, the two queries would be \n`What are the key themes of Great Gatsby?` and `What are the key themes of 1984?`.\nHere is the original user query to be transformed into answers:\n\n### Query:\n{message}\n\n### Response:\n",
        "input_types": {"num_outputs": "int", "message": "str"},
    }

    r2r_app = (
        R2RAppBuilder(config)
        .with_pipe_factory(R2RPipeFactoryWithMultiSearch)
        .build(
            # Add optional override arguments which propagate to the pipe factory
            multi_inner_search_pipe_override=web_search_pipe,
            query_generation_template_override=synthetic_query_generation_template,
        )
    )

    # Run the RAG pipeline through the R2R application
    result = r2r_app.rag(
        "Who was aristotle?",
        # query_transform_generation_config=GenerationConfig(model="gpt-4o"),
        rag_generation_config=GenerationConfig(model="gpt-3.5-turbo"),
    )

    print(f"Final Result:\n\n{result}")
