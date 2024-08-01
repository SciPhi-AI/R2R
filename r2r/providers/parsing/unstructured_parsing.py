from typing import Any, AsyncGenerator

from unstructured.partition.auto import partition

from r2r.base import Document, DocumentType, ParsingProvider


class UnstructuredParsingProvider(ParsingProvider):
    async def parse(self, document: Document) -> AsyncGenerator[Any, None]:
        elements = partition(file=document.data)
        for element in elements:
            yield element

    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        return "unstructured"
