import asyncio
import os
from typing import Optional

import fire

from r2r import R2RClient, generate_id_from_label

class QuestionAndAnswerClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        user_id: Optional[str] = None,
    ):
        self.client = R2RClient(base_url="http://localhost:8000")
        self.user_id = user_id or str(generate_id_from_label("user_id"))

        root_path = os.path.dirname(os.path.abspath(__file__))
        self.default_files = [
            os.path.join(root_path, "..", "data", "aristotle.txt"),
            # Add more files here
        ]

    def ingest(self, file_paths: Optional[list[str]] = None):
        file_paths = file_paths or self.default_files

        ids = [
            str(generate_id_from_label(file_path.split(os.path.sep)[-1]))
            for file_path in file_paths
        ]

        metadatas = [
            {
                "title": file_path.split(os.path.sep)[-1],
                "user_id": self.user_id,
            }
            for file_path in file_paths
        ]

        response = self.client.ingest_files(
            metadatas=metadatas, files=file_paths, ids=ids
        )
        print(response)

    def search(self, query: str):
        results = self.client.search(
            query, search_filters={"user_id": self.user_id}
        )
        for result in results["results"]:
            print(result)
    
    def rag_completion(self, query: str, model: str = "ollama/llama2"):
        rag_generation_config = {
            "model": model,
        }

        response = self.client.rag(
            message=query,
            search_filters={"user_id": self.user_id},
            rag_generation_config=rag_generation_config,
            streaming=False,
        )
        print(response)

    def rag_completion_streaming(self, query: str, model: str = "ollama/llama2"):
        rag_generation_config = {
            "model": model
        }

        response = self.client.rag(
            message=query,
            search_filters={"user_id": self.user_id},
            rag_generation_config=rag_generation_config,
            streaming=True,
        )

        async def _stream_response():
            async for chunk in response:
                print(chunk, end="", flush=True)

        asyncio.run(_stream_response())

    def delete(self, document_id: str):
        response = self.client.delete(["document_id"], [document_id])
        print(response)

    def get_logs(self, pipeline_type: Optional[str] = None):
        response = self.client.get_logs(pipeline_type)
        print(response)


if __name__ == "__main__":
    fire.Fire(QuestionAndAnswerClient)
