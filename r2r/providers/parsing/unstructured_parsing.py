from typing import Any, AsyncGenerator

from r2r.base import Document, DocumentType, ParsingProvider


class UnstructuredParsingProvider(ParsingProvider):
    def __init__(self, config):
        try:
            from unstructured.partition.auto import partition

            self.partition = partition
        except ImportError:
            raise ImportError(
                "Please install the unstructured package to use the unstructured parsing provider."
            )
        super().__init__(config)

    async def parse(self, document: Document) -> AsyncGenerator[Any, None]:
        elements = self.partition(file=document.data)
        for element in elements:
            yield element

    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        return "unstructured"
