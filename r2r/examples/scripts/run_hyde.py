import fire

from r2r import R2RBuilder, R2RConfig
from r2r.base.abstractions.llm import GenerationConfig
from r2r.main.assembly.factory_extensions import R2RPipeFactoryWithMultiSearch


def main(task_prompt_name="hyde", query="Who was aristotle?"):
    # Load the configuration file
    config = R2RConfig.from_json()

    app = (
        R2RBuilder(config)
        .with_pipe_factory(R2RPipeFactoryWithMultiSearch)
        .build(
            # Add optional override arguments which propagate to the pipe factory
            task_prompt_name=task_prompt_name,
        )
    )

    # Run the RAG pipeline through the R2R application
    result = app.rag(
        query,
        query_transform_generation_config=GenerationConfig(model="gpt-4o"),
        rag_generation_config=GenerationConfig(model="gpt-3.5-turbo"),
    )

    print(f"Search Results:\n\n{result.search_results}")
    print(f"RAG Results:\n\n{result.completion}")


if __name__ == "__main__":
    fire.Fire(main)
