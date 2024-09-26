# TODO - cleanup type issues in this file that relate to `bytes`
import base64
import logging
import os
import time
from copy import copy
from io import BytesIO
from typing import Any, AsyncGenerator

import httpx
from unstructured_client import UnstructuredClient
from unstructured_client.models import operations, shared

from core import parsers
from core.base import (
    AsyncParser,
    Document,
    DocumentExtraction,
    DocumentType,
    generate_id_from_label,
)
from core.base.abstractions import R2RSerializable
from core.base.providers.ingestion import IngestionConfig, IngestionProvider

logger = logging.getLogger(__name__)


class FallbackElement(R2RSerializable):
    text: str
    metadata: dict[str, Any]


class UnstructuredIngestionConfig(IngestionConfig):
    pass


class UnstructuredIngestionProvider(IngestionProvider):

    R2R_FALLBACK_PARSERS = {
        DocumentType.GIF: [parsers.ImageParser],
        DocumentType.JPEG: [parsers.ImageParser],
        DocumentType.JPG: [parsers.ImageParser],
        DocumentType.PNG: [parsers.ImageParser],
        DocumentType.SVG: [parsers.ImageParser],
        DocumentType.MP3: [parsers.AudioParser],
        DocumentType.MP4: [parsers.MovieParser],
    }

    IMAGE_TYPES = {
        DocumentType.GIF,
        DocumentType.JPG,
        DocumentType.JPEG,
        DocumentType.PNG,
        DocumentType.SVG,
    }

    def __init__(self, use_api: bool, config: UnstructuredIngestionConfig):
        super().__init__(config)
        self.config: UnstructuredIngestionConfig = config
        if config.IngestionConfig:
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
                self.local_unstructured_url = os.environ[
                    "UNSTRUCTURED_LOCAL_URL"
                ]
            except KeyError as e:
                raise ValueError(
                    "UNSTRUCTURED_LOCAL_URL environment variable is not set"
                ) from e

            self.client = httpx.AsyncClient()

        super().__init__(config)
        self.parsers: dict[DocumentType, AsyncParser] = {}
        self._initialize_parsers()

    def _initialize_parsers(self):
        for doc_type, parser_infos in self.R2R_FALLBACK_PARSERS.items():
            for parser_info in parser_infos:
                if (
                    doc_type not in self.config.excluded_parsers
                    and doc_type not in self.parsers
                ):
                    # will choose the first parser in the list
                    self.parsers[doc_type] = parser_info()

    async def parse_fallback(
        self, file_content: bytes, document: Document, chunk_size: int
    ) -> AsyncGenerator[FallbackElement, None]:

        texts = self.parsers[document.type].ingest(  # type: ignore
            file_content, chunk_size=chunk_size
        )

        chunk_id = 0
        async for text in texts:  # type: ignore
            if text and text != "":
                yield FallbackElement(
                    text=text, metadata={"chunk_id": chunk_id}
                )
                chunk_id += 1

    async def parse(
        self, file_content: bytes, document: Document
    ) -> AsyncGenerator[DocumentExtraction, None]:

        t0 = time.time()
        if document.type in self.R2R_FALLBACK_PARSERS.keys():
            logger.info(
                f"Parsing {document.type}: {document.id} with fallback parser"
            )
            elements = []
            async for element in self.parse_fallback(
                file_content,
                document,
                chunk_size=self.config.chunking_config.get(
                    "combine_under_n_chars", 128
                ),
            ):
                elements.append(element)
        else:
            logger.info(
                f"Parsing {document.type}: {document.id} with unstructured"
            )
            if isinstance(file_content, bytes):
                file_content = BytesIO(file_content)  # type: ignore

            # TODO - Include check on excluded parsers here.
            if self.use_api:
                logger.info(f"Using API to parse document {document.id}")
                files = self.shared.Files(
                    content=file_content.read(),  # type: ignore
                    file_name=document.metadata.get("title", "unknown_file"),
                )

                req = self.operations.PartitionRequest(
                    self.shared.PartitionParameters(
                        files=files,
                        **self.config.chunking_config,
                    )
                )
                elements = self.client.general.partition(req)  # type: ignore
                elements = list(elements.elements)  # type: ignore

            else:
                logger.info(
                    f"Using local unstructured fastapi server to parse document {document.id}"
                )
                # Base64 encode the file content
                encoded_content = base64.b64encode(file_content.read()).decode(  # type: ignore
                    "utf-8"
                )

                logger.info(
                    f"Sending a request to {self.local_unstructured_url}/partition"
                )

                response = await self.client.post(
                    f"{self.local_unstructured_url}/partition",
                    json={
                        "file_content": encoded_content,  # Use encoded string
                        "chunking_config": self.config.chunking_config,
                    },
                    timeout=300,  # Adjust timeout as needed
                )

                elements = response.json().get("elements", [])

        iteration = 0  # if there are no chunks
        for iteration, element in enumerate(elements):
            if isinstance(element, FallbackElement):
                text = element.text
                metadata = copy(document.metadata)
                metadata.update(element.metadata)
            else:
                element_dict = (
                    element.to_dict()
                    if not isinstance(element, dict)
                    else element
                )
                text = element_dict.get("text", "")
                if text == "":
                    continue

                metadata = copy(document.metadata)
                for key, value in element_dict.items():
                    if key == "metadata":
                        for k, v in value.items():
                            if k not in metadata:
                                if k != "orig_elements":
                                    metadata[f"unstructured_{k}"] = v

            # indicate that the document was chunked using unstructured
            # nullifies the need for chunking in the pipeline
            metadata["partitioned_by_unstructured"] = True

            # creating the text extraction
            yield DocumentExtraction(
                id=generate_id_from_label(f"{document.id}-{iteration}"),
                document_id=document.id,
                user_id=document.user_id,
                collection_ids=document.collection_ids,
                data=text,
                metadata=metadata,
            )

        # TODO: explore why this is throwing inadvertedly
        # if iteration == 0:
        #     raise ValueError(f"No chunks found for document {document.id}")

        logger.debug(
            f"Parsed document with id={document.id}, title={document.metadata.get('title', None)}, "
            f"user_id={document.metadata.get('user_id', None)}, metadata={document.metadata} "
            f"into {iteration + 1} extractions in t={time.time() - t0:.2f} seconds."
        )

    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        return "unstructured_local"
