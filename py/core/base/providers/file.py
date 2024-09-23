from abc import ABC, abstractmethod
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID

from .base import Provider, ProviderConfig


class FileConfig(ProviderConfig):
    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["postgres"]


class FileProvider(Provider, ABC):
    @abstractmethod
    async def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        pass

    @abstractmethod
    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        pass

    @abstractmethod
    async def delete_file(self, document_id: UUID) -> bool:
        pass

    @abstractmethod
    async def get_files_overview(
        self,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        pass
