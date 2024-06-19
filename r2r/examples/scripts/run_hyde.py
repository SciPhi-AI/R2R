from r2r import R2RAppBuilder, R2RConfig, R2RPipeFactoryWithMultiSearch
from r2r.core.abstractions.llm import GenerationConfig

if __name__ == "__main__":
    # Load the configuration file
    config = R2RConfig.from_json()

    r2r_app = (
        R2RAppBuilder(config)
        .with_pipe_factory(R2RPipeFactoryWithMultiSearch)
        .build(
            # Add optional override arguments which propagate to the pipe factory
            task_prompt_name="hyde",
        )
    )

    # Run the RAG pipeline through the R2R application
    result = r2r_app.rag(
        "Who was aristotle?",
        query_transform_generation_config=GenerationConfig(model="gpt-4o"),
        rag_generation_config=GenerationConfig(model="gpt-3.5-turbo"),
    )

    print(f"Final Result:\n\n{result}")
