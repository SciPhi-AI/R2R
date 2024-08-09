from tests.regression.test_cases.base import BaseTest


class TestRetrieval(BaseTest):
    RAG_EXCLUSIONS = [
        f"root['results']['completion']['{field}']"
        for field in [
            "id",
            "system_fingerprint",
            "usage",
            "created",
        ]
    ] + ["root['results']['completion']['choices'][0]['message']['content']"]

    def __init__(self, client):
        super().__init__(client)
        self.set_exclude_paths("rag", TestRetrieval.RAG_EXCLUSIONS)

    def get_test_cases(self):
        return {
            # "search": lambda client: self.search_test(client),
            "rag": lambda client: self.rag_test(
                client,
            ),
        }

    # def search_test(self, client):
    #     return client.search("What was Uber's profit in 2020?")

    # def rag_test(self, client):
    #     return client.rag("What was Uber's profit in 2020?")

    def basic_rag_test(self, client):
        return client.rag("What was Uber's profit in 2020?")

    def hybrid_rag_test(self, client):
        return client.rag("Who is John Snow?", {"do_hybrid_search": True})

    def streaming_rag_test(self, client):
        response = client.rag(
            "What was Lyft's profit in 2020?",
            rag_generation_config={"stream": True},
        )
        return "".join([chunk for chunk in response])

    def custom_rag_test(self, client):
        return client.rag(
            "Who was Aristotle?",
            rag_generation_config={
                "model": "anthropic/claude-3-haiku-20240307",
                "temperature": 0.7,
            },
        )
