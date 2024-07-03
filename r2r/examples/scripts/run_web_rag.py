import fire

from r2r import R2RBuilder, SerperClient, WebSearchPipe
from r2r.base.abstractions.llm import GenerationConfig


def run_rag_pipeline(query="Who was Aristotle?"):
    # Create search pipe override and pipes
    web_search_pipe = WebSearchPipe(
        serper_client=SerperClient()  # TODO - Develop a `WebSearchProvider` for configurability
    )

    app = R2RBuilder().with_vector_search_pipe(web_search_pipe).build()

    # Run the RAG pipeline through the R2R application
    result = app.rag(
        query,
        rag_generation_config=GenerationConfig(model="gpt-4o"),
    )

    print(f"Search Results:\n\n{result.search_results}")
    print(f"RAG Results:\n\n{result.completion}")


if __name__ == "__main__":
    fire.Fire(run_rag_pipeline)
