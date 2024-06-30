import asyncio
import logging
import os
import time
import uuid
from typing import Optional

import fire
from fastapi.datastructures import UploadFile

from r2r import (
    R2R,
    AnalysisTypes,
    Document,
    FilterCriteria,
    KGSearchSettings,
    R2RBuilder,
    R2RClient,
    R2RConfig,
    VectorSearchSettings,
    generate_id_from_label,
)
from r2r.base.abstractions.llm import GenerationConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class R2RQuickstart:
    """A demo class for the R2R library."""

    USER_IDS = [
        "063edaf8-3e63-4cb9-a4d6-a855f36376c3",
        "45c3f5a8-bcbe-43b1-9b20-51c07fd79f14",
        "c6c23d85-6217-4caa-b391-91ec0021a000",
        None,
    ]

    def __init__(
        self,
        config_name: Optional[str] = None,
        config_path: Optional[str] = None,
        file_tuples: Optional[list[tuple]] = None,
        client_server_mode: bool = False,
        base_url: Optional[str] = None,
    ):
        if config_path and config_name:
            raise ValueError("Cannot specify both config and config_name")
        if not config_name and not config_path:
            config_name = "default"

        if config_path:
            config = R2RConfig.from_json(config_path)
        else:
            config = R2RConfig.from_json(
                R2RBuilder.CONFIG_OPTIONS[config_name]
            )

        if base_url and not client_server_mode:
            raise ValueError(
                "base_url is provided but client_server_mode is not set to True"
            )

        if client_server_mode:
            self.base_url = base_url or "http://localhost:8000"
            self.client = R2RClient(self.base_url)
            logger.info(
                f"Running in client-server mode with base_url: {self.base_url}"
            )
        else:
            self.app = R2R(config=config)
            logger.info("Running locally")

        root_path = os.path.dirname(os.path.abspath(__file__))
        self.user_ids = [
            uuid.UUID(user_id) if user_id else None
            for user_id in self.USER_IDS
        ]
        self.default_files = [
            os.path.join(root_path, "data", "aristotle.txt"),
            os.path.join(root_path, "data", "got.txt"),
            os.path.join(root_path, "data", "screen_shot.png"),
            os.path.join(root_path, "data", "pg_essay_1.html"),
            os.path.join(root_path, "data", "pg_essay_2.html"),
            os.path.join(root_path, "data", "pg_essay_3.html"),
            os.path.join(root_path, "data", "pg_essay_4.html"),
            os.path.join(root_path, "data", "pg_essay_5.html"),
            os.path.join(root_path, "data", "lyft_2021.pdf"),
            os.path.join(root_path, "data", "uber_2021.pdf"),
            os.path.join(root_path, "data", "sample.mp3"),
            os.path.join(root_path, "data", "sample2.mp3"),
        ]

        self.file_tuples = file_tuples or [
            (
                os.path.join(root_path, "data", "aristotle.txt"),
                os.path.join(root_path, "data", "aristotle_v2.txt"),
            )
        ]

    def ingest_documents(self, file_paths: Optional[str] = None):
        file_paths = (
            file_paths.split(",") if file_paths else self.default_files
        )
        documents = []
        t0 = time.time()

        for index, file_path in enumerate(file_paths):
            with open(file_path, "rb") as f:
                data = f.read()
            documents.append(
                Document(
                    id=generate_id_from_label(
                        file_path.split(os.path.sep)[-1]
                    ),
                    data=data,
                    type=file_path.split(".")[-1],
                    metadata={
                        "user_id": self.user_ids[index % len(self.user_ids)],
                        "title": file_path.split(os.path.sep)[-1],
                    },
                )
            )

        if hasattr(self, "client"):
            documents_dicts = [doc.dict() for doc in documents]
            response = self.client.ingest_documents(
                documents_dicts, monitor=True
            )
        else:
            response = self.app.ingest_documents(documents)

        t1 = time.time()
        print(f"Time taken to ingest files: {t1-t0:.2f} seconds")
        print(response)

    def update_documents(self, file_tuples: Optional[list[tuple]] = None):
        file_tuples = file_tuples or self.file_tuples
        documents = []
        t0 = time.time()

        for index, (old_file, new_file) in enumerate(file_tuples):
            with open(new_file, "rb") as f:
                data = f.read()

            documents.append(
                Document(
                    id=generate_id_from_label(old_file.split(os.path.sep)[-1]),
                    data=data,
                    type=new_file.split(".")[-1],
                    metadata={
                        "user_id": self.user_ids[index % len(self.user_ids)],
                        "title": new_file.split(os.path.sep)[-1],
                    },
                )
            )

        if hasattr(self, "client"):
            documents_dicts = [doc.dict() for doc in documents]
            response = self.client.update_documents(
                documents_dicts, monitor=True
            )
        else:
            response = self.app.update_documents(documents)

        t1 = time.time()
        print(f"Time taken to update documents: {t1-t0:.2f} seconds")
        print(response)

    # ingests a single file
    def ingest(self, file_paths: Optional[str] = None):
        self.ingest_files(file_paths or self.default_files[0])

    def ingest_files(self, file_paths: Optional[str] = None, no_media=False):
        file_paths = (
            file_paths.split(",") if file_paths else self.default_files
        )

        if no_media:
            excluded_types = ["jpeg", "jpg", "png", "svg", "mp3", "mp4"]
            file_paths = [
                file_path
                for file_path in file_paths
                if file_path.split(".")[-1] not in excluded_types
            ]

        ids = [
            generate_id_from_label(file_path.split(os.path.sep)[-1])
            for file_path in file_paths
        ]

        files = [
            UploadFile(
                filename=file_path,
                file=open(file_path, "rb"),
            )
            for file_path in file_paths
        ]

        for file in files:
            file.file.seek(0, 2)
            file.size = file.file.tell()
            file.file.seek(0)

        user_ids = [
            self.user_ids[index % len(self.user_ids)]
            for index in range(len(file_paths))
        ]
        t0 = time.time()

        if hasattr(self, "client"):
            response = self.client.ingest_files(
                metadatas=None,
                file_paths=file_paths,
                document_ids=ids,
                user_ids=user_ids,
                monitor=True,
            )
        else:
            metadatas = [{} for _ in file_paths]
            response = self.app.ingest_files(
                files=files,
                metadatas=metadatas,
                document_ids=ids,
                user_ids=user_ids,
            )
        t1 = time.time()
        print(f"Time taken to ingest files: {t1-t0:.2f} seconds")
        print(response)

    def update_files(self, file_tuples: Optional[list[tuple]] = None):
        file_tuples = file_tuples or self.file_tuples
        new_files = [
            UploadFile(
                filename=new_file,
                file=open(new_file, "rb"),
            )
            for old_file, new_file in file_tuples
        ]

        for file in new_files:
            file.file.seek(0, 2)
            file.size = file.file.tell()
            file.file.seek(0)

        metadatas = [
            {
                "title": old_file,
                "user_id": self.user_ids[index % len(self.user_ids)],
            }
            for index, (old_file, new_file) in enumerate(file_tuples)
        ]
        t0 = time.time()

        if hasattr(self, "client"):
            response = self.client.update_files(
                metadatas=metadatas,
                files=[new for old, new in file_tuples],
                document_ids=[
                    generate_id_from_label(old_file.split(os.path.sep)[-1])
                    for old_file, new_file in file_tuples
                ],
                monitor=True,
            )
        else:
            response = self.app.update_files(
                files=new_files,
                document_ids=[
                    generate_id_from_label(old_file.split(os.path.sep)[-1])
                    for old_file, new_file in file_tuples
                ],
            )
        t1 = time.time()
        print(f"Time taken to update files: {t1-t0:.2f} seconds")
        print(response)

    def search(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_agent_generation_config: Optional[dict] = None,
    ):
        kg_agent_generation_config = (
            GenerationConfig(**kg_agent_generation_config)
            if kg_agent_generation_config
            else GenerationConfig(model="gpt-4o")
        )

        t0 = time.time()
        if hasattr(self, "client"):
            results = self.client.search(
                query,
                use_vector_search,
                search_filters,
                search_limit,
                do_hybrid_search,
                use_kg_search,
                kg_agent_generation_config,
            )
        else:
            results = self.app.search(
                query,
                VectorSearchSettings(
                    use_vector_search=use_vector_search,
                    search_filters=search_filters or {},
                    search_limit=search_limit,
                    do_hybrid_search=do_hybrid_search,
                ),
                KGSearchSettings(
                    use_kg_search=use_kg_search,
                    agent_generation_config=kg_agent_generation_config,
                ),
            )

        if isinstance(results, dict) and "results" in results:
            results = results["results"]

        if "vector_search_results" in results:
            print("Vector search results:")
            for result in results["vector_search_results"]:
                print(result)
        if "kg_search_results" in results and results["kg_search_results"]:
            print("KG search results:", results["kg_search_results"])

        t1 = time.time()
        print(f"Time taken to search: {t1-t0:.2f} seconds")

    def rag(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_agent_generation_config: Optional[dict] = None,
        stream: bool = False,
        rag_generation_config: Optional[GenerationConfig] = None,
    ):
        t0 = time.time()

        kg_agent_generation_config = (
            GenerationConfig(**kg_agent_generation_config)
            if kg_agent_generation_config
            else GenerationConfig(model="gpt-4o")
        )

        rag_generation_config = (
            GenerationConfig(**rag_generation_config, stream=stream)
            if rag_generation_config
            else GenerationConfig(model="gpt-4o", stream=stream)
        )

        if hasattr(self, "client"):
            response = self.client.rag(
                query=query,
                use_vector_search=use_vector_search,
                search_filters=search_filters or {},
                search_limit=search_limit,
                do_hybrid_search=do_hybrid_search,
                use_kg_search=use_kg_search,
                kg_agent_generation_config=kg_agent_generation_config,
                rag_generation_config=rag_generation_config,
            )
            if not stream:
                response = response["results"]
                t1 = time.time()
                print(f"Time taken to get RAG response: {t1-t0:.2f} seconds")
                print(f"Search Results:\n{response['search_results']}")
                print(f"Completion:\n{response['completion']}")

            else:
                for chunk in response:
                    print(chunk, end="", flush=True)
                t1 = time.time()
                print(
                    f"\nTime taken to stream RAG response: {t1-t0:.2f} seconds"
                )
        else:
            response = self.app.rag(
                query,
                vector_search_settings=VectorSearchSettings(
                    use_vector_search=use_vector_search,
                    search_filters=search_filters or {},
                    search_limit=search_limit,
                    do_hybrid_search=do_hybrid_search,
                ),
                kg_search_settings=KGSearchSettings(
                    use_kg_search=use_kg_search,
                    agent_generation_config=kg_agent_generation_config,
                ),
                rag_generation_config=rag_generation_config,
            )

            if not stream:
                t1 = time.time()
                print(f"Time taken to get RAG response: {t1-t0:.2f} seconds")
                print(f"Time taken to get RAG response: {t1-t0:.2f} seconds")
                print(f"Search Results:\n{response.search_results}")
                print(f"Completion:\n{response.completion}")
            else:

                async def _stream_response():
                    async for chunk in response:
                        print(chunk, end="", flush=True)

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

        t0 = time.time()
        if hasattr(self, "client"):
            response = self.client.evaluate(
                query=query,
                context=context,
                completion=completion,
            )
        else:
            response = self.app.evaluate(
                query=query,
                context=context,
                completion=completion,
                eval_generation_config=(
                    GenerationConfig(**eval_generation_config)
                    if eval_generation_config
                    else GenerationConfig(model="gpt-3.5-turbo")
                ),
            )

        t1 = time.time()
        print(f"Time taken to evaluate: {t1-t0:.2f} seconds")
        print(response)

    def delete(
        self,
        keys: list[str] = ["document_id"],
        values: list[str] = ["c9bdbac7-0ea3-5c9e-b590-018bd09b127b"],
        version: Optional[str] = None,
    ):
        if version:
            keys.append("version")
            values.append(version)
        t0 = time.time()
        if hasattr(self, "client"):
            response = self.client.delete(keys, values)
        else:
            response = self.app.delete(keys, values)
        t1 = time.time()
        print(f"Time taken to delete: {t1-t0:.2f} seconds")
        print(response)

    def logs(self, log_type_filter: Optional[str] = None):
        t0 = time.time()
        if hasattr(self, "client"):
            response = self.client.logs(log_type_filter)
        else:
            t0 = time.time()
            response = self.app.logs(log_type_filter)
        t1 = time.time()
        print(f"Time taken to get logs: {t1-t0:.2f} seconds")
        print(response)

    def documents_overview(
        self,
        document_ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ):
        t0 = time.time()
        if hasattr(self, "client"):
            results = self.client.documents_overview(document_ids, user_ids)

        else:
            t0 = time.time()
            results = self.app.documents_overview(document_ids, user_ids)

        if isinstance(results, dict) and "results" in results:
            results = results["results"]

        for document in results:
            print(document)

        t1 = time.time()
        print(f"Time taken to get document info: {t1-t0:.2f} seconds")

    def document_chunks(self, document_id: str):
        t0 = time.time()

        # Convert the string to UUID
        doc_uuid = uuid.UUID(document_id)

        if hasattr(self, "client"):
            results = self.client.document_chunks(doc_uuid)
        else:
            results = self.app.document_chunks(doc_uuid)
            for chunk in results:
                print(chunk)

        if isinstance(results, dict) and "results" in results:
            results = results["results"]

        for document in results:
            print(document)

        t1 = time.time()
        print(f"Time taken to get document chunks: {t1-t0:.2f} seconds")

    def app_settings(self):
        t0 = time.time()
        if hasattr(self, "client"):
            response = self.client.app_settings()
        else:
            t0 = time.time()
            response = self.app.app_settings()
        t1 = time.time()
        print(f"Time taken to get app data: {t1-t0:.2f} seconds")
        print(response)

    def users_overview(self, user_ids: Optional[list[uuid.UUID]] = None):
        user_ids = user_ids or [
            ele for ele in self.user_ids if ele is not None
        ]
        t0 = time.time()
        if hasattr(self, "client"):
            response = self.client.users_overview(user_ids)
        else:
            t0 = time.time()
            response = self.app.users_overview(user_ids)

        if isinstance(response, dict) and "results" in response:
            response = response["results"]

        for user in response:
            print(user)

        t1 = time.time()
        print(f"Time taken to get user stats: {t1-t0:.2f} seconds")

    def analytics(
        self,
        filters: Optional[str] = None,
        analysis_types: Optional[str] = None,
    ):
        t0 = time.time()
        filter_criteria = FilterCriteria(filters=filters)
        analysis_types = AnalysisTypes(analysis_types=analysis_types)

        if hasattr(self, "client"):
            response = self.client.analytics(
                filter_criteria=filter_criteria.model_dump(),
                analysis_types=analysis_types.model_dump(),
            )
        else:
            response = self.app.analytics(
                filter_criteria=filter_criteria, analysis_types=analysis_types
            )

        t1 = time.time()
        print(f"Time taken to get analytics: {t1-t0:.2f} seconds")
        print(response)

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        self.app.serve(host, port)

    def get_app(self):
        return self.app.app.app


if __name__ == "__main__":
    fire.Fire(R2RQuickstart)
