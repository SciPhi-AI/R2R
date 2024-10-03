from tests.regression.test_cases.base import BaseTest


class TestRetrieval(BaseTest):
    RAG_EXCLUSIONS = (
        [
            f"root['completion']['{field}']"
            for field in [
                "id",
                "system_fingerprint",
                "usage",
                "created",
            ]
        ]
        + ["root['completion']['choices'][0]['message']['content']"]
        + [f"root['search_results'][{i}]['score']" for i in range(10)]
    )

    def __init__(self, client):
        super().__init__(client)
        # ignore scores since math epsilon fails for nested floats, exact text is sufficient.
        self.set_exclude_paths(
            "search",
            [
                f"root['vector_search_results'][{i}]['score']"
                for i in range(10)
            ],
        )
        self.set_exclude_paths("basic_rag", TestRetrieval.RAG_EXCLUSIONS)
        self.set_exclude_paths("hybrid_rag", TestRetrieval.RAG_EXCLUSIONS)
        self.set_exclude_paths("streaming_rag", TestRetrieval.RAG_EXCLUSIONS)

    def get_test_cases(self):
        return {
            "search": lambda client: self.search_test(client),
            "basic_rag": lambda client: self.basic_rag_test(client),
            "hybrid_rag": lambda client: self.hybrid_rag_test(client),
            "streaming_rag": lambda client: self.streaming_rag_test(client),
        }

    def search_test(self, client):
        try:
            return client.search("What is the capital of France?")
        except Exception as e:
            return {"results": str(e)}

    def hybrid_search_test(self, client):
        try:
            return client.search(
                "What is the capital of France?", {"use_hybrid_search": True}
            )
        except Exception as e:
            return {"results": str(e)}

    def basic_rag_test(self, client):
        try:
            return client.rag("What was Uber's profit in 2020?")
        except Exception as e:
            return {"results": str(e)}

    def hybrid_rag_test(self, client):
        try:
            return client.rag("Who is Jon Snow?", {"use_hybrid_search": True})
        except Exception as e:
            return {"results": str(e)}

    def streaming_rag_test(self, client):
        try:
            response = client.rag(
                "What was Lyft's profit in 2020?",
                rag_generation_config={"stream": True},
            )
            return {
                "results": {
                    "completion": {
                        "choices": [
                            {
                                "message": {
                                    "content": f"{''.join([chunk for chunk in response])}"
                                }
                            }
                        ]
                    }
                }
            }
        except Exception as e:
            return {"results": str(e)}
