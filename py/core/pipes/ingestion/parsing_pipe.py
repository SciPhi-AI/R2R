import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from core.base import AsyncState, DatabaseProvider, Document, DocumentChunk
from core.base.abstractions import R2RDocumentProcessingError
from core.base.pipes.base_pipe import AsyncPipe
from core.base.providers.ingestion import IngestionProvider
from core.utils import generate_extraction_id
from shared.abstractions import PDFParsingError, PopperNotFoundError

logger = logging.getLogger()


class ParsingPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: Document

    def __init__(
        self,
        database_provider: DatabaseProvider,
        ingestion_provider: IngestionProvider,
        config: AsyncPipe.PipeConfig,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
            *args,
            **kwargs,
        )
        self.database_provider = database_provider
        self.ingestion_provider = ingestion_provider

    async def _parse(
        self,
        document: Document,
        run_id: UUID,
        version: str,
        ingestion_config_override: Optional[dict],
    ) -> AsyncGenerator[DocumentChunk, None]:
        try:
            ingestion_config_override = ingestion_config_override or {}
            override_provider = ingestion_config_override.pop("provider", None)
            if (
                override_provider
                and override_provider
                != self.ingestion_provider.config.provider
            ):
                raise ValueError(
                    f"Provider '{override_provider}' does not match ingestion provider '{self.ingestion_provider.config.provider}'."
                )
            if result := await self.database_provider.files_handler.retrieve_file(
                document.id
            ):
                file_name, file_wrapper, file_size = result

            with file_wrapper as file_content_stream:
                file_content = file_content_stream.read()

            async for extraction in self.ingestion_provider.parse(  # type: ignore
                file_content, document, ingestion_config_override
            ):
                id = generate_extraction_id(extraction.id, version=version)
                extraction.id = id
                extraction.metadata["version"] = version
                yield extraction
        except (PopperNotFoundError, PDFParsingError) as e:
            raise R2RDocumentProcessingError(
                error_message=e.message,
                document_id=document.id,
                status_code=e.status_code,
            )
        except Exception as e:
            raise R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Error parsing document: {str(e)}",
            )

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args,
        **kwargs,
    ) -> AsyncGenerator[DocumentChunk, None]:
        ingestion_config = kwargs.get("ingestion_config")

        async for result in self._parse(
            input.message,
            run_id,
            input.message.metadata.get("version", "v0"),
            ingestion_config_override=ingestion_config,
        ):
            yield result
