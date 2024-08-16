import logging
import time
from io import BytesIO
from typing import AsyncGenerator

from r2r.base import (
    Document,
    DocumentExtraction,
    DocumentType,
    ParsingProvider,
    generate_id_from_label,
)

logger = logging.getLogger(__name__)


class UnstructuredParsingProvider(ParsingProvider):
    def __init__(self, config):
        try:
            from unstructured.partition.auto import partition

            self.partition = partition
        except ImportError:
            raise ImportError(
                "Please install the unstructured package to use the unstructured parsing provider."
            )
        if config.excluded_parsers:
            logger.warning(
                "Excluded parsers are not supported by the unstructured parsing provider."
            )
        super().__init__(config)

    async def parse(
        self, document: Document
    ) -> AsyncGenerator[DocumentExtraction, None]:
        data = document.data
        if isinstance(data, bytes):
            data = BytesIO(data)

        # TODO - Include check on excluded parsers here.

        t0 = time.time()
        elements = self.partition(file=data)

        for iteration, element in enumerate(elements):
            extraction = DocumentExtraction(
                id=generate_id_from_label(f"{document.id}-{iteration}"),
                document_id=document.id,
                user_id=document.user_id,
                group_ids=document.group_ids,
                data=element.text,
                metadata=document.metadata,
            )
            yield extraction

        logger.debug(
            f"Parsed document with id={document.id}, title={document.metadata.get('title', None)}, "
            f"user_id={document.metadata.get('user_id', None)}, metadata={document.metadata} "
            f"into {iteration + 1} extractions in t={time.time() - t0:.2f} seconds."
        )

    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        return "unstructured"
