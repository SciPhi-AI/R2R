# TODO - cleanup type issues in this file that relate to `bytes`
import base64
import logging
import os
import time
from copy import copy
from io import BytesIO
from typing import Any, AsyncGenerator, Optional

import httpx
from unstructured_client import UnstructuredClient
from unstructured_client.models import operations, shared

from core import parsers
from core.base import (
    AsyncParser,
    ChunkingStrategy,
    Document,
    DocumentExtraction,
    DocumentType,
)
from core.base.abstractions import R2RSerializable
from core.base.providers.ingestion import IngestionConfig, IngestionProvider
from core.utils import generate_extraction_id

logger = logging.getLogger(__name__)


class FallbackElement(R2RSerializable):
    text: str
    metadata: dict[str, Any]


class UnstructuredIngestionConfig(IngestionConfig):
    combine_under_n_chars: int = 128
    max_characters: int = 500
    new_after_n_chars: int = 1500

    coordinates: Optional[bool] = None
    encoding: Optional[str] = None  # utf-8
    extract_image_block_types: Optional[list[str]] = None
    gz_uncompressed_content_type: Optional[str] = None
    hi_res_model_name: Optional[str] = None
    include_orig_elements: Optional[bool] = None
    include_page_breaks: Optional[bool] = None

    languages: Optional[list[str]] = None
    multipage_sections: Optional[bool] = None
    ocr_languages: Optional[list[str]] = None
    # output_format: Optional[str] = "application/json"
    overlap: Optional[int] = None
    overlap_all: Optional[bool] = None
    pdf_infer_table_structure: Optional[bool] = None

    similarity_threshold: Optional[float] = None
    skip_infer_table_types: Optional[list[str]] = None
    split_pdf_concurrency_level: Optional[int] = None
    split_pdf_page: Optional[bool] = None
    starting_page_number: Optional[int] = None
    strategy: Optional[str] = None
    chunking_strategy: Optional[ChunkingStrategy] = None
    unique_element_ids: Optional[bool] = None
    xml_keep_tags: Optional[bool] = None

    def to_ingestion_request(self):
        import json

        x = json.loads(self.json())
        x.pop("extra_fields", None)
        x.pop("provider", None)
        x.pop("excluded_parsers", None)

        x = {k: v for k, v in x.items() if v is not None}
        return x


class UnstructuredIngestionProvider(IngestionProvider):
    R2R_FALLBACK_PARSERS = {
        DocumentType.GIF: [parsers.ImageParser],
        DocumentType.JPEG: [parsers.ImageParser],
        DocumentType.JPG: [parsers.ImageParser],
        DocumentType.PNG: [parsers.ImageParser],
        DocumentType.SVG: [parsers.ImageParser],
        DocumentType.MP3: [parsers.AudioParser],
        DocumentType.JSON: [parsers.JSONParser],  # type: ignore
        DocumentType.HTML: [parsers.HTMLParser],  # type: ignore
        DocumentType.XLSX: [parsers.XLSXParser],  # type: ignore
    }

    IMAGE_TYPES = {
        DocumentType.GIF,
        DocumentType.JPG,
        DocumentType.JPEG,
        DocumentType.PNG,
        DocumentType.SVG,
    }

    def __init__(self, config: UnstructuredIngestionConfig):
        super().__init__(config)
        self.config: UnstructuredIngestionConfig = config
        if config.provider == "unstructured_api":
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
        self,
        file_content: bytes,
        document: Document,
        ingestion_config_override: dict,
    ) -> AsyncGenerator[DocumentExtraction, None]:

        ingestion_config = {
            **self.config.to_ingestion_request(),
            **(ingestion_config_override or {}),
        }
        # cleanup extra fields
        ingestion_config.pop("provider", None)
        ingestion_config.pop("excluded_parsers", None)

        t0 = time.time()
        if document.type in self.R2R_FALLBACK_PARSERS.keys():
            logger.info(
                f"Parsing {document.type}: {document.id} with fallback parser"
            )
            elements = []
            async for element in self.parse_fallback(
                file_content,
                document,
                chunk_size=self.config.combine_under_n_chars,
            ):
                elements.append(element)
        else:
            logger.info(
                f"Parsing {document.type}: {document.id} with unstructured"
            )
            if isinstance(file_content, bytes):
                file_content = BytesIO(file_content)  # type: ignore

            # TODO - Include check on excluded parsers here.
            if self.config.provider == "unstructured_api":
                logger.info(f"Using API to parse document {document.id}")
                files = self.shared.Files(
                    content=file_content.read(),  # type: ignore
                    file_name=document.metadata.get("title", "unknown_file"),
                )

                req = self.operations.PartitionRequest(
                    self.shared.PartitionParameters(
                        files=files,
                        **ingestion_config,
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
                        "ingestion_config": ingestion_config,
                        "filename": document.metadata.get("title", None),
                    },
                    timeout=3600,  # Adjust timeout as needed
                )

                if response.status_code != 200:
                    logger.error(f"Error partitioning file: {response.text}")
                    raise ValueError(
                        f"Error partitioning file: {response.text}"
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
            metadata["chunk_order"] = iteration
            # creating the text extraction
            yield DocumentExtraction(
                id=generate_extraction_id(document.id, iteration),
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
