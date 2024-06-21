import fire

from r2r import R2RAppBuilder, SerperClient, WebSearchPipe
from r2r.core.abstractions.llm import GenerationConfig


def run_rag_pipeline(query="Who was Aristotle?"):
    # Create search pipe override and pipes
    web_search_pipe = WebSearchPipe(
        serper_client=SerperClient()  # TODO - Develop a `WebSearchProvider` for configurability
    )

    r2r_app = R2RAppBuilder().with_search_pipe(web_search_pipe).build()

    # Run the RAG pipeline through the R2R application
    result = r2r_app.rag(
        query,
        rag_generation_config=GenerationConfig(model="gpt-4o"),
    )

    print(f"Final Result:\n\n{result}")


if __name__ == "__main__":
    fire.Fire(run_rag_pipeline)
