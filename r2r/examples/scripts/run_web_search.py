from r2r import GenerationConfig, R2RAppBuilder, R2RWebSearchPipe, SerperClient

if __name__ == "__main__":
    # Create search pipe override and pipes
    web_search_pipe = R2RWebSearchPipe(
        serper_client=SerperClient()  # TODO - Develop a `WebSearchProvider` for configurability
    )

    r2r_app = R2RAppBuilder().with_search_pipe(web_search_pipe).build()

    # Run the RAG pipeline through the R2R application
    result = r2r_app.rag(
        "Who was aristotle?",
        rag_generation_config=GenerationConfig(model="gpt-4o"),
    )

    print(f"Final Result:\n\n{result}")
