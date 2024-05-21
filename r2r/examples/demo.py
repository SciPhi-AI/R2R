"""A demo script for the R2R library."""
import asyncio
import json
import logging
import os
import time
from typing import Optional

import fire
from fastapi.datastructures import UploadFile

from r2r import (
    Document,
    GenerationConfig,
    R2RApp,
    R2RClient,
    R2RConfig,
    R2RPipelineFactory,
    R2RProviderFactory,
    generate_id_from_label,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class R2RDemo:
    DEMO_USER_ID = "063edaf8-3e63-4cb9-a4d6-a855f36376c3"

    """A demo class for the R2R library."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        file_list: Optional[list[str]] = None,
        user_id: str = DEMO_USER_ID,
        base_url: Optional[str] = None,
    ):
        if base_url:
            self.client = R2RClient(base_url)
        else:
            config = R2RConfig.from_json(config_path=config_path)
            providers = R2RProviderFactory(config).create_providers()
            pipelines = R2RPipelineFactory(
                config, providers
            ).create_pipelines()
            self.r2r = R2RApp(config, providers, pipelines)

        root_path = os.path.dirname(os.path.abspath(__file__))
        self.user_id = user_id
        self.default_files = file_list or [
            os.path.join(root_path, "data", "screen_shot.png"),
            os.path.join(root_path, "data", "aristotle.txt"),
            os.path.join(root_path, "data", "pg_essay_1.html"),
            os.path.join(root_path, "data", "pg_essay_2.html"),
            os.path.join(root_path, "data", "pg_essay_3.html"),
            os.path.join(root_path, "data", "pg_essay_4.html"),
            os.path.join(root_path, "data", "pg_essay_5.html"),
            os.path.join(root_path, "data", "lyft_2021.pdf"),
            os.path.join(root_path, "data", "uber_2021.pdf"),
        ]

    def ingest_as_documents(self, file_paths: Optional[list[str]] = None):
        file_paths = file_paths or self.default_files
        documents = []
        for file_path in file_paths:
            with open(file_path, "rb") as f:
                data = f.read()

            documents.append(
                Document(
                    id=generate_id_from_label(file_path),
                    data=data,
                    type=file_path.split(".")[-1],
                    metadata={
                        "title": file_path.split(os.path.sep)[-1],
                        "user_id": self.user_id,
                    },
                )
            )

        if hasattr(self, "client"):
            documents_dicts = [doc.dict() for doc in documents]
            t0 = time.time()
            response = self.client.ingest_documents(documents_dicts)
            t1 = time.time()
            print(f"Time taken to ingest files: {t1-t0:.2f} seconds")
            print(response)
        else:
            t0 = time.time()
            self.r2r.ingest_documents(documents)
            t1 = time.time()
            print(f"Time taken to ingest files: {t1-t0:.2f} seconds")

    def ingest_as_files(self, file_paths: Optional[list[str]] = None):
        file_paths = file_paths or self.default_files
        files = [
            UploadFile(
                filename=file_path.split(os.path.sep)[-1],
                file=open(file_path, "rb"),
            )
            for file_path in file_paths
        ]

        # Set file size manually
        for file in files:
            file.file.seek(0, 2)  # Move to the end of the file
            file.size = file.file.tell()  # Get the file size
            file.file.seek(0)  # Move back to the start of the file

        metadatas = [
            {
                "title": file_path.split(os.path.sep)[-1],
                "user_id": self.user_id,
            }
            for file_path in file_paths
        ]

        if hasattr(self, "client"):
            t0 = time.time()
            response = self.client.ingest_files(
                metadatas=metadatas, files=file_paths
            )
            t1 = time.time()
            print(f"Time taken to ingest files: {t1-t0:.2f} seconds")
            print(response)
        else:
            t0 = time.time()
            self.r2r.ingest_files(files=files, metadatas=metadatas)
            t1 = time.time()
            print(f"Time taken to ingest files: {t1-t0:.2f} seconds")

    def search(self, query: str):
        if hasattr(self, "client"):
            t0 = time.time()
            results = self.client.search(
                query, search_filters={"user_id": self.user_id}
            )
            t1 = time.time()
            print(f"Time taken to search: {t1-t0:.2f} seconds")
            for result in results["results"]:
                print(result)
        else:
            t0 = time.time()
            results = self.r2r.search(
                query, search_filters={"user_id": self.user_id}
            )
            t1 = time.time()
            print(f"Time taken to search: {t1-t0:.2f} seconds")
            for result in results["results"]:
                print(result)

    def rag(
        self,
        query: str,
        rag_generation_config: Optional[dict] = None,
        streaming: bool = False,
    ):
        if hasattr(self, "client"):
            if not streaming:
                t0 = time.time()
                response = self.client.rag(
                    query,
                    search_filters={"user_id": self.user_id},
                    streaming=streaming,
                    rag_generation_config=rag_generation_config,
                )
                t1 = time.time()
                print(f"Time taken to get RAG response: {t1-t0:.2f} seconds")
                print(response)
            else:
                t0 = time.time()

                response = self.client.rag(
                    query,
                    search_filters={"user_id": self.user_id},
                    streaming=streaming,
                    rag_generation_config=rag_generation_config,
                )
                collector = ""
                for chunk in response:
                    collector += chunk
                t1 = time.time()
                print(
                    f"\nTime taken to stream RAG response: {t1-t0:.2f} seconds"
                )
        else:
            t0 = time.time()
            rag_generation_config = (
                GenerationConfig(**rag_generation_config, streaming=streaming)
                if rag_generation_config
                else GenerationConfig(
                    **{"streaming": streaming, "model": "gpt-3.5-turbo"}
                )
            )
            response = self.r2r.rag(
                query,
                search_filters={"user_id": self.user_id},
                rag_generation_config=rag_generation_config,
            )

            if not streaming:
                t1 = time.time()
                print(f"Time taken to get RAG response: {t1-t0:.2f} seconds")
                print(response)
            else:

                async def _stream_response():
                    async for chunk in response:
                        print(chunk, end="")

                asyncio.run(_stream_response())
                t1 = time.time()
                print(
                    f"\nTime taken to stream RAG response: {t1-t0:.2f} seconds"
                )

    def evaluate(
        self,
        query: Optional[str] = None,
        context: Optional[str] = None,
        completion: Optional[str] = None,
        eval_generation_config: Optional[dict] = None,
    ):
        if not query:
            query = "What is the meaning of life?"
        if not context:
            context = """Search Results:
            1. The meaning of life is 42.
            2. The car is red.
            3. The meaning of life is to help others.
            4. The car is blue.
            5. The meaning of life is to learn and grow.
            6. The car is green.
            7. The meaning of life is to make a difference.
            8. The car is yellow.
            9. The meaning of life is to enjoy the journey.
            10. The car is black.
            """
        if not completion:
            completion = "The meaning of life is to help others, learn and grow, and to make a difference."

        if hasattr(self, "client"):
            t0 = time.time()
            response = self.client.evaluate(
                query=query,
                context=context,
                completion=completion,
            )
            t1 = time.time()
            print(f"Time taken to evaluate: {t1-t0:.2f} seconds")
            print(response)
        else:
            t0 = time.time()
            response = self.r2r.evaluate(
                query=query,
                context=context,
                completion=completion,
                eval_generation_config=GenerationConfig(
                    **eval_generation_config
                )
                if eval_generation_config
                else None,
            )
            t1 = time.time()
            print(f"Time taken to evaluate: {t1-t0:.2f} seconds")
            print(response)

    def delete(
        self,
        key: str = "document_id",
        value: str = "15255e98-e245-5b58-a57f-6c51babf72dd",
    ):
        if hasattr(self, "client"):
            t0 = time.time()
            response = self.client.delete(key, value)
            t1 = time.time()
            print(f"Time taken to delete: {t1-t0:.2f} seconds")
            print(response)
        else:
            t0 = time.time()
            response = self.r2r.delete(key, value)
            t1 = time.time()
            print(f"Time taken to delete: {t1-t0:.2f} seconds")
            print(response)

    def get_user_ids(self):
        if hasattr(self, "client"):
            t0 = time.time()
            response = self.client.get_user_ids()
            t1 = time.time()
            print(f"Time taken to get user IDs: {t1-t0:.2f} seconds")
            print(response)
        else:
            t0 = time.time()
            response = self.r2r.get_user_ids()
            t1 = time.time()
            print(f"Time taken to get user IDs: {t1-t0:.2f} seconds")
            print(response)

    def get_user_document_data(self):
        if hasattr(self, "client"):
            t0 = time.time()
            response = self.client.get_user_document_data(self.user_id)
            t1 = time.time()
            print(f"Time taken to get user document data: {t1-t0:.2f} seconds")
            print(response)
        else:
            t0 = time.time()
            response = self.r2r.get_user_document_data(self.user_id)
            t1 = time.time()
            print(f"Time taken to get user document data: {t1-t0:.2f} seconds")
            print(response)

    def get_logs(self, pipeline_type: Optional[str] = None):
        if hasattr(self, "client"):
            t0 = time.time()
            response = self.client.get_logs(pipeline_type)
            t1 = time.time()
            print(f"Time taken to get logs: {t1-t0:.2f} seconds")
            print(response)
        else:
            t0 = time.time()
            response = self.r2r.get_logs(pipeline_type)
            t1 = time.time()
            print(f"Time taken to get logs: {t1-t0:.2f} seconds")
            print(response)

    def get_open_api_endpoint(self):
        if hasattr(self, "client"):
            print(
                json.dumps(
                    self.client.get_open_api_endpoint()["results"], indent=2
                )
            )
        else:
            print(
                json.dumps(
                    self.r2r.get_open_api_endpoint()["results"], indent=2
                )
            )

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        self.r2r.serve(host, port)


if __name__ == "__main__":
    fire.Fire(R2RDemo)
