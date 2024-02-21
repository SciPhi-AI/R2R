from abc import ABC, abstractmethod
from typing import Any, Generator, Optional


class DatasetConfig:
    def __init__(
        self,
        name: str,
        data_files: Optional[list[str]] = None,
        max_entries: Optional[int] = None,
        text_field: Optional[str] = None,
        split: Optional[str] = "train",
    ):
        """
        Initialize the dataset configuration.

        Args:
            name (str): The name of the dataset.
            data_files (Optional[list[str]]): Specific data files or patterns to load from the dataset.
            max_entries (Optional[int]): Maximum number of entries to stream from the dataset. None for unlimited.
            text_field (Optional[str]): The specific field in the dataset to treat as the main text content.
        """
        self.name = name
        self.data_files = data_files or []
        self.max_entries = max_entries
        self.text_field = text_field
        self.split = split


class DatasetProvider(ABC):
    supported_providers = ["huggingface", "pdf"]

    def __init__(self, provider: str) -> None:
        if provider not in self.supported_providers:
            raise ValueError(
                f"Error, `{provider}` is not in DatasetProvider's list of supported providers."
            )

    @abstractmethod
    def load_datasets(
        self,
        dataset_configs: list[DatasetConfig],
        split: str = "train",
        streaming: bool = True,
    ) -> None:
        """
        Abstract method to load multiple datasets based on their configurations.

        Args:
            dataset_configs (list[DatasetConfig]): Configurations for each dataset to load.
            split (str): The specific split of the dataset to load, e.g., 'train', 'test'.
            streaming (bool): Whether to stream the dataset or load it entirely.
        """
        pass

    @abstractmethod
    def stream_text(self) -> Generator[Any, None, None]:
        """
        Abstract method to stream dataset entries across all configured datasets.

        Yields:
            entry (Dict[str, Any]): A dictionary representing a single dataset entry.
        """
        pass
