import asyncio

import fire

from r2r.client import R2RClient


class WebRAGClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.client = R2RClient(base_url)

    def search(self, query, search_limit=25, rerank_limit=15):
        search_response = self.client.search(
            query,
            search_limit=search_limit,
            rerank_limit=rerank_limit,
        )
        for i, response in enumerate(search_response):
            link = response["metadata"].get("link", "")
            title = response["metadata"].get("title", "")
            body = response["metadata"].get("snippet", "")
            print(f"Result {i + 1}: {link}")
            print(f"Title: {title}")
            print(f"Body:\n{body[:500]}\n")

    def rag_completion(
        self,
        query,
        model="gpt-4-turbo-preview",
        search_limit=25,
        rerank_limit=15,
    ):
        rag_response = self.client.rag_completion(
            query,
            search_limit=search_limit,
            rerank_limit=rerank_limit,
            generation_config={"model": model},
        )
        print("rag_response = ", rag_response)

    def rag_completion_streaming(self, query, model="gpt-4-turbo-preview"):
        async def stream_rag_completion():
            async for chunk in self.client.stream_rag_completion(
                query,
                5,
                generation_config={"stream": True, "model": model},
            ):
                print(chunk, end="", flush=True)

        asyncio.run(stream_rag_completion())

    def get_logs(self):
        print("Fetching logs after all steps...")
        logs_response = self.client.get_logs()
        print(f"Logs response:\n{logs_response}\n")

    def get_logs_summary(self):
        print("Fetching logs summary after all steps...")
        logs_summary_response = self.client.get_logs_summary()
        print(f"Logs summary response:\n{logs_summary_response}\n")

if __name__ == "__main__":
    fire.Fire(WebRAGClient)
