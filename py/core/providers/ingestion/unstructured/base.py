# TODO - cleanup type issues in this file that relate to `bytes`
import asyncio
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
    ChunkingStrategy,
    Document,
    DocumentChunk,
    DocumentType,
    RecursiveCharacterTextSplitter,
)
from core.base.abstractions import R2RSerializable
from core.base.providers.ingestion import IngestionConfig, IngestionProvider
from core.utils import generate_extraction_id

from ...database import PostgresDatabaseProvider
from ...llm import (
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)

logger = logging.getLogger()


class FallbackElement(R2RSerializable):
    text: str
    metadata: dict[str, Any]


class UnstructuredIngestionConfig(IngestionConfig):
    combine_under_n_chars: int = 128
    max_characters: int = 500
    new_after_n_chars: int = 1500
    overlap: int = 64

    coordinates: bool | None = None
    encoding: str | None = None  # utf-8
    extract_image_block_types: list[str] | None = None
    gz_uncompressed_content_type: str | None = None
    hi_res_model_name: str | None = None
    include_orig_elements: bool | None = None
    include_page_breaks: bool | None = None

    languages: list[str] | None = None
    multipage_sections: bool | None = None
    ocr_languages: list[str] | None = None
    # output_format: Optional[str] = "application/json"
    overlap_all: bool | None = None
    pdf_infer_table_structure: bool | None = None

    similarity_threshold: float | None = None
    skip_infer_table_types: list[str] | None = None
    split_pdf_concurrency_level: int | None = None
    split_pdf_page: bool | None = None
    starting_page_number: int | None = None
    strategy: str | None = None
    chunking_strategy: str | ChunkingStrategy | None = None  # type: ignore
    unique_element_ids: bool | None = None
    xml_keep_tags: bool | None = None

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
        DocumentType.GIF: [parsers.ImageParser],  # type: ignore
        DocumentType.JPEG: [parsers.ImageParser],  # type: ignore
        DocumentType.JPG: [parsers.ImageParser],  # type: ignore
        DocumentType.PNG: [parsers.ImageParser],  # type: ignore
        DocumentType.SVG: [parsers.ImageParser],  # type: ignore
        DocumentType.HEIC: [parsers.ImageParser],  # type: ignore
        DocumentType.MP3: [parsers.AudioParser],  # type: ignore
        DocumentType.JSON: [parsers.JSONParser],  # type: ignore
        DocumentType.HTML: [parsers.HTMLParser],  # type: ignore
        DocumentType.XLS: [parsers.XLSParser],  # type: ignore
        DocumentType.XLSX: [parsers.XLSXParser],  # type: ignore
        DocumentType.DOC: [parsers.DOCParser],  # type: ignore
        DocumentType.PPT: [parsers.PPTParser],  # type: ignore
    }

    EXTRA_PARSERS = {
        DocumentType.CSV: {"advanced": parsers.CSVParserAdvanced},  # type: ignore
        DocumentType.PDF: {
            "unstructured": parsers.PDFParserUnstructured,  # type: ignore
            "zerox": parsers.VLMPDFParser,  # type: ignore
        },
        DocumentType.XLSX: {"advanced": parsers.XLSXParserAdvanced},  # type: ignore
    }

    IMAGE_TYPES = {
        DocumentType.GIF,
        DocumentType.HEIC,
        DocumentType.JPG,
        DocumentType.JPEG,
        DocumentType.PNG,
        DocumentType.SVG,
    }

    def __init__(
        self,
        config: UnstructuredIngestionConfig,
        database_provider: PostgresDatabaseProvider,
        llm_provider: (
            LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
    ):
        super().__init__(config, database_provider, llm_provider)
        self.config: UnstructuredIngestionConfig = config
        self.database_provider: PostgresDatabaseProvider = database_provider
        self.llm_provider: (
            LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ) = llm_provider

        if config.provider == "unstructured_api":
            try:
                self.unstructured_api_auth = os.environ["UNSTRUCTURED_API_KEY"]
            except KeyError as e:
                raise ValueError(
                    "UNSTRUCTURED_API_KEY environment variable is not set"
                ) from e

            self.unstructured_api_url = os.environ.get(
                "UNSTRUCTURED_API_URL",
                "https://api.unstructuredapp.io/general/v0/general",
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
                    "UNSTRUCTURED_SERVICE_URL"
                ]
            except KeyError as e:
                raise ValueError(
                    "UNSTRUCTURED_SERVICE_URL environment variable is not set"
                ) from e

            self.client = httpx.AsyncClient()

        self.parsers: dict[DocumentType, AsyncParser] = {}
        self._initialize_parsers()

    def _initialize_parsers(self):
        for doc_type, parsers in self.R2R_FALLBACK_PARSERS.items():
            for parser in parsers:
                if (
                    doc_type not in self.config.excluded_parsers
                    and doc_type not in self.parsers
                ):
                    # will choose the first parser in the list
                    self.parsers[doc_type] = parser(
                        config=self.config,
                        database_provider=self.database_provider,
                        llm_provider=self.llm_provider,
                    )
        # TODO - Reduce code duplication between Unstructured & R2R
        for doc_type, doc_parser_name in self.config.extra_parsers.items():
            self.parsers[f"{doc_parser_name}_{str(doc_type)}"] = (
                UnstructuredIngestionProvider.EXTRA_PARSERS[doc_type][
                    doc_parser_name
                ](
                    config=self.config,
                    database_provider=self.database_provider,
                    llm_provider=self.llm_provider,
                )
            )

    async def parse_fallback(
        self,
        file_content: bytes,
        ingestion_config: dict,
        parser_name: str,
    ) -> AsyncGenerator[FallbackElement, None]:
        contents = []
        async for chunk in self.parsers[parser_name].ingest(  # type: ignore
            file_content, **ingestion_config
        ):  # type: ignore
            if isinstance(chunk, dict) and chunk.get("content"):
                contents.append(chunk)
            elif chunk:  # Handle string output for backward compatibility
                contents.append({"content": chunk})

        if not contents:
            logging.warning(
                "No valid text content was extracted during parsing"
            )
            return

        logging.info(f"Fallback ingestion with config = {ingestion_config}")

        iteration = 0
        for content_item in contents:
            text = content_item["content"]

            loop = asyncio.get_event_loop()
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=ingestion_config["new_after_n_chars"],
                chunk_overlap=ingestion_config["overlap"],
            )
            chunks = await loop.run_in_executor(
                None, splitter.create_documents, [text]
            )

            for text_chunk in chunks:
                metadata = {"chunk_id": iteration}
                if "page_number" in content_item:
                    metadata["page_number"] = content_item["page_number"]

                yield FallbackElement(
                    text=text_chunk.page_content,
                    metadata=metadata,
                )
                iteration += 1
                await asyncio.sleep(0)

    async def parse(
        self,
        file_content: bytes,
        document: Document,
        ingestion_config_override: dict,
    ) -> AsyncGenerator[DocumentChunk, None]:
        ingestion_config = copy(
            {
                **self.config.to_ingestion_request(),
                **(ingestion_config_override or {}),
            }
        )
        # cleanup extra fields
        ingestion_config.pop("provider", None)
        ingestion_config.pop("excluded_parsers", None)

        t0 = time.time()
        parser_overrides = ingestion_config_override.get(
            "parser_overrides", {}
        )
        elements = []

        # TODO - Cleanup this approach to be less hardcoded
        # TODO - Remove code duplication between Unstructured & R2R
        if document.document_type.value in parser_overrides:
            logger.info(
                f"Using parser_override for {document.document_type} with input value {parser_overrides[document.document_type.value]}"
            )
            async for element in self.parse_fallback(
                file_content,
                ingestion_config=ingestion_config,
                parser_name=f"zerox_{DocumentType.PDF.value}",
            ):
                elements.append(element)

        elif document.document_type in self.R2R_FALLBACK_PARSERS.keys():
            logger.info(
                f"Parsing {document.document_type}: {document.id} with fallback parser"
            )
            async for element in self.parse_fallback(
                file_content,
                ingestion_config=ingestion_config,
                parser_name=document.document_type,
            ):
                elements.append(element)
        else:
            logger.info(
                f"Parsing {document.document_type}: {document.id} with unstructured"
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

                ingestion_config.pop("app", None)
                ingestion_config.pop("extra_parsers", None)

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
                    element if isinstance(element, dict) else element.to_dict()
                )
                text = element_dict.get("text", "")
                if text == "":
                    continue

                metadata = copy(document.metadata)
                for key, value in element_dict.items():
                    if key == "metadata":
                        for k, v in value.items():
                            if k not in metadata and k != "orig_elements":
                                metadata[f"unstructured_{k}"] = v

            # indicate that the document was chunked using unstructured
            # nullifies the need for chunking in the pipeline
            metadata["partitioned_by_unstructured"] = True
            metadata["chunk_order"] = iteration
            # creating the text extraction
            yield DocumentChunk(
                id=generate_extraction_id(document.id, iteration),
                document_id=document.id,
                owner_id=document.owner_id,
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
