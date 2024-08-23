import fire

from r2r import R2RBuilder, SerperClient, WebSearchPipe


def run_rag_pipeline():
    # Create search pipe override and pipes
    web_search_pipe = WebSearchPipe(
        serper_client=SerperClient()  # TODO - Develop a `WebSearchProvider` for configurability
    )

    app = R2RBuilder().with_vector_search_pipe(web_search_pipe).build()

    app.serve()


if __name__ == "__main__":
    fire.Fire(run_rag_pipeline)
