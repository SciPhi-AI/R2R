import ast
import asyncio
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, Optional, Union

import click
from fastapi import UploadFile

from r2r.base import (
    AnalysisTypes,
    FilterCriteria,
    KGSearchSettings,
    VectorSearchSettings,
)
from r2r.base.abstractions.llm import GenerationConfig

from .api.client import R2RClient
from .assembly.builder import R2RBuilder
from .assembly.config import R2RConfig
from .r2r import R2R


class R2RExecutionWrapper:
    """A demo class for the R2R library."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_name: Optional[str] = "default",
        client_mode: bool = True,
        base_url="http://localhost:8000",
    ):
        if config_path and config_name:
            raise Exception("Cannot specify both config_path and config_name")

        # Handle fire CLI
        if isinstance(client_mode, str):
            client_mode = client_mode.lower() == "true"
        self.client_mode = client_mode
        self.base_url = base_url

        if self.client_mode:
            self.client = R2RClient(base_url)
            self.app = None
        else:
            config = (
                R2RConfig.from_json(config_path)
                if config_path
                else R2RConfig.from_json(
                    R2RBuilder.CONFIG_OPTIONS[config_name or "default"]
                )
            )

            self.client = None
            self.app = R2R(config=config)

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        if not self.client_mode:
            self.app.serve(host, port)
        else:
            raise ValueError(
                "Serve method is only available when `client_mode=False`."
            )

    def _parse_metadata_string(metadata_string: str) -> list[dict]:
        """
        Convert a string representation of metadata into a list of dictionaries.

        The input string can be in one of two formats:
        1. JSON array of objects: '[{"key": "value"}, {"key2": "value2"}]'
        2. Python-like list of dictionaries: "[{'key': 'value'}, {'key2': 'value2'}]"

        Args:
        metadata_string (str): The string representation of metadata.

        Returns:
        list[dict]: A list of dictionaries representing the metadata.

        Raises:
        ValueError: If the string cannot be parsed into a list of dictionaries.
        """
        if not metadata_string:
            return []

        try:
            # First, try to parse as JSON
            return json.loads(metadata_string)
        except json.JSONDecodeError as e:
            try:
                # If JSON parsing fails, try to evaluate as a Python literal
                result = ast.literal_eval(metadata_string)
                if not isinstance(result, list) or not all(
                    isinstance(item, dict) for item in result
                ):
                    raise ValueError(
                        "The string does not represent a list of dictionaries"
                    ) from e
                return result
            except (ValueError, SyntaxError) as exc:
                raise ValueError(
                    "Unable to parse the metadata string. "
                    "Please ensure it's a valid JSON array or Python list of dictionaries."
                ) from exc

    def ingest_files(
        self,
        file_paths: list[str],
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[Union[uuid.UUID, str]]] = None,
        versions: Optional[list[str]] = None,
    ):
        if isinstance(file_paths, str):
            file_paths = list(file_paths.split(","))
        if isinstance(metadatas, str):
            metadatas = self._parse_metadata_string(metadatas)
        if isinstance(document_ids, str):
            document_ids = list(document_ids.split(","))
        if isinstance(versions, str):
            versions = list(versions.split(","))

        all_file_paths = []
        for path in file_paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    all_file_paths.extend(
                        os.path.join(root, file) for file in files
                    )
            else:
                all_file_paths.append(path)

        files = [
            UploadFile(
                filename=os.path.basename(file_path),
                file=open(file_path, "rb"),
            )
            for file_path in all_file_paths
        ]

        for file in files:
            file.file.seek(0, 2)
            file.size = file.file.tell()
            file.file.seek(0)

        try:
            spinner_chars = "|/-\\"
            stop_spinner = False

            def spinner():
                i = 0
                while not stop_spinner:
                    click.echo(
                        f"\rIngesting files {spinner_chars[i % len(spinner_chars)]}",
                        nl=False,
                    )
                    time.sleep(0.1)
                    i += 1

            spinner_thread = threading.Thread(target=spinner)
            spinner_thread.start()

            try:
                if self.client_mode:
                    results = self.client.ingest_files(
                        file_paths=all_file_paths,
                        document_ids=document_ids,
                        metadatas=metadatas,
                        versions=versions,
                    )["results"]
                else:
                    results = self.app.ingest_files(
                        files=files,
                        document_ids=document_ids,
                        metadatas=metadatas,
                        versions=versions,
                    )
            finally:
                stop_spinner = True
                spinner_thread.join()
                click.echo("\rIngestion complete!    ")

            return results
        finally:
            for file in files:
                file.file.close()

    def update_files(
        self,
        file_paths: list[str],
        document_ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ):
        if isinstance(file_paths, str):
            file_paths = list(file_paths.split(","))
        if isinstance(metadatas, str):
            metadatas = self._parse_metadata_string(metadatas)
        if isinstance(document_ids, str):
            document_ids = list(document_ids.split(","))

        if self.client_mode:
            return self.client.update_files(
                file_paths=file_paths,
                document_ids=document_ids,
                metadatas=metadatas,
            )["results"]

        files = [
            UploadFile(
                filename=file_path,
                file=open(file_path, "rb"),
            )
            for file_path in file_paths
        ]
        return self.app.update_files(
            files=files, document_ids=document_ids, metadatas=metadatas
        )

    def search(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_search_generation_config: Optional[dict] = None,
    ):
        if self.client_mode:
            return self.client.search(
                query,
                use_vector_search,
                search_filters,
                search_limit,
                do_hybrid_search,
                use_kg_search,
                kg_search_generation_config,
            )["results"]
        else:
            return self.app.search(
                query,
                VectorSearchSettings(
                    use_vector_search=use_vector_search,
                    search_filters=search_filters or {},
                    search_limit=search_limit,
                    do_hybrid_search=do_hybrid_search,
                ),
                KGSearchSettings(
                    use_kg_search=use_kg_search,
                    kg_search_generation_config=GenerationConfig(
                        **(kg_search_generation_config or {})
                    ),
                ),
            )

    def rag(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_search_generation_config: Optional[dict] = None,
        stream: bool = False,
        rag_generation_config: Optional[dict] = None,
    ):
        if self.client_mode:
            response = self.client.rag(
                query=query,
                use_vector_search=use_vector_search,
                search_filters=search_filters or {},
                search_limit=search_limit,
                do_hybrid_search=do_hybrid_search,
                use_kg_search=use_kg_search,
                kg_search_generation_config=kg_search_generation_config,
                rag_generation_config=rag_generation_config,
            )
            if not stream:
                response = response["results"]
                return response
            else:
                return response
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
                    kg_search_generation_config=GenerationConfig(
                        **(kg_search_generation_config or {})
                    ),
                ),
                rag_generation_config=GenerationConfig(
                    **(rag_generation_config or {})
                ),
            )
            if not stream:
                return response
            else:

                async def async_generator():
                    async for chunk in response:
                        yield chunk

                def sync_generator():
                    try:
                        loop = asyncio.get_event_loop()
                        async_gen = async_generator()
                        while True:
                            try:
                                yield loop.run_until_complete(
                                    async_gen.__anext__()
                                )
                            except StopAsyncIteration:
                                break
                    except Exception:
                        pass

                return sync_generator()

    def documents_overview(
        self,
        document_ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ):
        if self.client_mode:
            return self.client.documents_overview(document_ids, user_ids)[
                "results"
            ]
        else:
            return self.app.documents_overview(document_ids, user_ids)

    def delete(
        self,
        keys: list[str],
        values: list[str],
    ):
        if self.client_mode:
            return self.client.delete(keys, values)["results"]
        else:
            return self.app.delete(keys, values)

    def logs(self, log_type_filter: Optional[str] = None):
        if self.client_mode:
            return self.client.logs(log_type_filter)["results"]
        else:
            return self.app.logs(log_type_filter)

    def document_chunks(self, document_id: str):
        doc_uuid = uuid.UUID(document_id)
        if self.client_mode:
            return self.client.document_chunks(doc_uuid)["results"]
        else:
            return self.app.document_chunks(doc_uuid)

    def app_settings(self):
        if self.client_mode:
            return self.client.app_settings()
        else:
            return self.app.app_settings()

    def users_overview(self, user_ids: Optional[list[uuid.UUID]] = None):
        if self.client_mode:
            return self.client.users_overview(user_ids)["results"]
        else:
            return self.app.users_overview(user_ids)

    def analytics(
        self,
        filters: Optional[Dict[str, Any]] = None,
        analysis_types: Optional[Dict[str, Any]] = None,
    ):
        if self.client_mode:
            return self.client.analytics(
                filter_criteria=filters,
                analysis_types=analysis_types,
            )["results"]

        filter_criteria = FilterCriteria(filters=filters)
        analysis_types_obj = AnalysisTypes(analysis_types=analysis_types)
        return self.app.analytics(
            filter_criteria=filter_criteria, analysis_types=analysis_types_obj
        )

    def ingest_sample_file(self, no_media: bool = True, option: int = 0):
        from r2r.examples.scripts.sample_data_ingestor import (
            SampleDataIngestor,
        )

        """Ingest the first sample file into R2R."""
        sample_ingestor = SampleDataIngestor(self)
        return sample_ingestor.ingest_sample_file(
            no_media=no_media, option=option
        )

    def ingest_sample_files(self, no_media: bool = True):
        from r2r.examples.scripts.sample_data_ingestor import (
            SampleDataIngestor,
        )

        """Ingest the first sample file into R2R."""
        sample_ingestor = SampleDataIngestor(self)
        return sample_ingestor.ingest_sample_files(no_media=no_media)

    def inspect_knowledge_graph(self, limit: int = 100) -> str:
        if self.client_mode:
            return self.client.inspect_knowledge_graph(limit)["results"]
        else:
            return self.engine.inspect_knowledge_graph(limit)

    def health(self) -> str:
        if self.client_mode:
            return self.client.health()

    def get_app(self):
        if not self.client_mode:
            return self.app.app.app
        else:
            raise Exception(
                "`get_app` method is only available when running with `client_mode=False`."
            )


if __name__ == "__main__":
    import fire

    fire.Fire(R2RExecutionWrapper)
