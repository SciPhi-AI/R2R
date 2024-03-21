import json
from abc import ABC, abstractmethod
from typing import Any, Union
from uuid import UUID


class VectorEntry:
    def __init__(
        self, entry_id: UUID, vector: list[float], metadata: dict[str, Any]
    ):
        self.vector = vector
        self.id = entry_id
        self.metadata = metadata

    def to_json(self) -> str:
        """Serialize the object to a JSON string."""
        return json.dumps(
            {"id": self.id, "vector": self.vector, "metadata": self.metadata},
            default=lambda o: o.__dict__,
        )

    @staticmethod
    def from_json(json_str: str) -> "VectorEntry":
        """Deserialize a JSON string into a VectorEntry object."""
        data = json.loads(json_str)
        return VectorEntry(
            vector=data["vector"],
            entry_id=data["id"],
            metadata=data["metadata"],
        )

    def __str__(self) -> str:
        """Return a string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"


class VectorSearchResult:
    def __init__(
        self, entry_id: str, score: float, metadata: dict[str, Any]
    ) -> None:
        self.id = entry_id
        self.score = score
        self.metadata = metadata

    def __str__(self) -> str:
        """Return a string representation of the VectorSearchResult."""
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorSearchResult for debugging."""
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def to_dict(self) -> dict:
        """Return a dictionary representation of the VectorSearchResult."""
        return {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata,
        }


class VectorDBProvider(ABC):
    supported_providers = ["local", "pgvector", "qdrant"]

    def __init__(self, provider: str):
        if provider not in VectorDBProvider.supported_providers:
            raise ValueError(
                f"Error, `{provider}` is not in VectorDBProvider's list of supported providers."
            )

    @abstractmethod
    def initialize_collection(
        self, collection_name: str, dimension: int
    ) -> None:
        pass

    @abstractmethod
    def copy(self, entry: VectorEntry, commit: bool = True) -> None:
        pass

    @abstractmethod
    def upsert(self, entry: VectorEntry, commit: bool = True) -> None:
        pass

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    def create_index(self, index_type, column_name, index_options):
        pass

    @abstractmethod
    def close(self):
        pass

    def upsert_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        for entry in entries:
            self.upsert(entry, commit=commit)

    def copy_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        for entry in entries:
            self.copy(entry, commit=commit)

    @abstractmethod
    def filtered_deletion(
        self, key: str, value: Union[bool, int, str]
    ) -> None:
        pass

    @abstractmethod
    def get_all_unique_values(
        self, metadata_field: str, filters: dict = {}
    ) -> list:
        pass
