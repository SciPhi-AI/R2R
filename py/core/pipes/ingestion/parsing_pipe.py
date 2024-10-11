import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    Document,
    DocumentExtraction,
    FileProvider,
    IngestionConfig,
    PipeType,
    RunLoggingSingleton,
)
from core.base.abstractions import R2RDocumentProcessingError
from core.base.pipes.base_pipe import AsyncPipe
from core.base.providers.ingestion import IngestionProvider
from core.utils import generate_extraction_id

logger = logging.getLogger(__name__)


class ParsingPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: Document

    def __init__(
        self,
        ingestion_provider: IngestionProvider,
        file_provider: FileProvider,
        config: AsyncPipe.PipeConfig,
        type: PipeType = PipeType.INGESTOR,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
            type,
            pipe_logger,
            *args,
            **kwargs,
        )
        self.ingestion_provider = ingestion_provider
        self.file_provider = file_provider

    async def _parse(
        self,
        document: Document,
        run_id: UUID,
        version: str,
        ingestion_config_override: Optional[dict],
    ) -> AsyncGenerator[DocumentExtraction, None]:
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
            if result := await self.file_provider.retrieve_file(document.id):
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
    ) -> AsyncGenerator[DocumentExtraction, None]:
        ingestion_config = kwargs.get("ingestion_config")

        async for result in self._parse(
            input.message,
            run_id,
            input.message.metadata.get("version", "v0"),
            ingestion_config_override=ingestion_config,
        ):
            yield result
