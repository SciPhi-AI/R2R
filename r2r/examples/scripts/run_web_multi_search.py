import fire

from r2r import (
    R2RAppBuilder,
    R2RPipeFactoryWithMultiSearch,
    SerperClient,
    WebSearchPipe,
)
from r2r.core.abstractions.llm import GenerationConfig


def run_rag_pipeline(query="Who was Aristotle?"):
    # Initialize a web search pipe
    web_search_pipe = WebSearchPipe(serper_client=SerperClient())

    # Define a new synthetic query generation template
    synthetic_query_generation_template = {
        "template": """
            ### Instruction:
            Given the following query, write a double newline separated list of up to {num_outputs} advanced queries meant to help answer the original query.
            DO NOT generate any single query which is likely to require information from multiple distinct documents.
            EACH single query will be used to carry out a cosine similarity semantic search over distinct indexed documents.
            FOR EXAMPLE, if asked `how do the key themes of Great Gatsby compare with 1984`, the two queries would be
            `What are the key themes of Great Gatsby?` and `What are the key themes of 1984?`.
            Here is the original user query to be transformed into answers:

            ### Query:
            {message}

            ### Response:
            """,
        "input_types": {"num_outputs": "int", "message": "str"},
    }

    # Build the R2R application with the custom pipeline
    r2r_app = (
        R2RAppBuilder()
        .with_pipe_factory(R2RPipeFactoryWithMultiSearch)
        .build(
            # override inputs consumed in building the MultiSearchPipe
            multi_inner_search_pipe_override=web_search_pipe,
            query_generation_template_override=synthetic_query_generation_template,
        )
    )

    # Run the RAG pipeline through the R2R application
    result = r2r_app.rag(
        query,
        rag_generation_config=GenerationConfig(model="gpt-4o"),
    )

    print(f"Final Result:\n\n{result}")


if __name__ == "__main__":
    fire.Fire(run_rag_pipeline)
