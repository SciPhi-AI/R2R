from typing import Any, AsyncGenerator

from r2r.base import Document, DocumentType, ParsingConfig, ParsingProvider


class R2RParsingProvider(ParsingProvider):
    def __init__(self, config: ParsingConfig):
        super().__init__(config)
        self.parsers = {}  # Initialize parsers as in the original ParsingPipe

    async def parse(self, document: Document) -> AsyncGenerator[Any, None]:
        parser = self.get_parser_for_document_type(document.type)
        texts = parser.ingest(document.data)
        async for text in texts:
            yield text

    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        for override in self.config.override_parsers:
            if override.document_type == doc_type:
                return override.parser
        return self.config.strategy.value
