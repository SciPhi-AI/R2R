import logging
import os
import time
from io import BytesIO
from typing import AsyncGenerator

from unstructured.chunking.basic import chunk_elements
from unstructured_client import UnstructuredClient
from unstructured_client.models import operations, shared

from core.base import (
    Document,
    DocumentExtraction,
    DocumentType,
    ParsingProvider,
    generate_id_from_label,
)

logger = logging.getLogger(__name__)


class UnstructuredParsingProvider(ParsingProvider):
    def __init__(self, use_api, config):
        if config.excluded_parsers:
            logger.warning(
                "Excluded parsers are not supported by the unstructured parsing provider."
            )

        self.use_api = use_api
        if self.use_api:
            try:
                self.unstructured_api_auth = os.environ["UNSTRUCTURED_API_KEY"]
            except KeyError as e:
                raise ValueError(
                    "UNSTRUCTURED_API_KEY environment variable is not set"
                ) from e

            self.unstructured_api_url = os.environ.get(
                "UNSTRUCTURED_API_URL",
                "https://api.unstructured.io/general/v0/general",
            )

            self.client = UnstructuredClient(
                api_key_auth=self.unstructured_api_auth,
                server_url=self.unstructured_api_url,
            )
            self.shared = shared
            self.operations = operations

        else:
            try:
                from unstructured.partition.auto import partition

                self.partition = partition

            except ImportError as e:
                raise ImportError(
                    "Please install the unstructured package to use the unstructured parsing provider."
                ) from e

        super().__init__(config)

    async def parse(
        self, file_content: bytes, document: Document
    ) -> AsyncGenerator[DocumentExtraction, None]:
        if isinstance(file_content, bytes):
            file_content = BytesIO(file_content)

        # TODO - Include check on excluded parsers here.
        print('self.config.chunking_config = ', self.config.chunking_config)
        t0 = time.time()
        if self.use_api:
            logger.info(f"Using API to parse document {document.id}")
            files = self.shared.Files(
                content=file_content.read(),
                file_name=document.metadata.get("title", "unknown_file"),
            )

            req = self.operations.PartitionRequest(
                self.shared.PartitionParameters(
                    files=files, **self.config.chunking_config.dict()
                )
            )
            elements = self.client.general.partition(req)
            elements = list(elements.elements)

        else:
            logger.info(
                f"Using local unstructured to parse document {document.id}"
            )
            elements = self.partition(
                file=file_content, **self.config.chunking_config.extra_fields['chunking_config']
            )            
        
        for iteration, element in enumerate(elements):
            if not isinstance(element, dict):
                element = element.to_dict()

            for key, value in elements.items():
                if key == "text":
                    text = value
                elif key == "metadata":
                    for k, v in value.items():
                        if k not in document.metadata:
                            document.metadata[k] = v
                        else:
                            document.metadata[f"unstructured_{k}"] = v
                elif key in document.metadata:
                    document.metadata[f"unstructured_{key}"] = value
                else:
                    document.metadata[key] = value

            # indicate that the document was chunked using unstructured
            # nullifies the need for chunking in the pipeline
            document.metadata["partitioned_by_unstructured"] = True

            # creating the text extraction
            yield DocumentExtraction(
                id=generate_id_from_label(f"{document.id}-{iteration}"),
                document_id=document.id,
                user_id=document.user_id,
                group_ids=document.group_ids,
                data=text,
                metadata=document.metadata,
            )

        logger.debug(
            f"Parsed document with id={document.id}, title={document.metadata.get('title', None)}, "
            f"user_id={document.metadata.get('user_id', None)}, metadata={document.metadata} "
            f"into {iteration + 1} extractions in t={time.time() - t0:.2f} seconds."
        )

    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        return "unstructured_local"
