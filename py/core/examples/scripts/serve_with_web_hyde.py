import fire

from core import R2RBuilder, SerperClient, WebSearchPipe
from core.base.abstractions.llm import GenerationConfig
from core.main.assembly.factory_extensions import R2RPipeFactoryWithMultiSearch


def run_rag_pipeline():
    # Initialize a web search pipe
    web_search_pipe = WebSearchPipe(serper_client=SerperClient())

    # Define a new synthetic query generation template
    synthetic_query_generation_template = {
        "name": "synthetic_query_generation_template",
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
    (
        R2RBuilder()
        .with_pipe_factory(R2RPipeFactoryWithMultiSearch)
        .build(
            # override inputs consumed in building the MultiSearchPipe
            multi_inner_search_pipe_override=web_search_pipe,
            query_generation_template_override=synthetic_query_generation_template,
        )
    ).serve()


if __name__ == "__main__":
    fire.Fire(run_rag_pipeline)
