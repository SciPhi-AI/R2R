import logging
from typing import Generator, Optional, Tuple

from r2r.core import DatasetConfig, DatasetProvider

logger = logging.getLogger(__name__)


class HuggingFaceDataProvider(DatasetProvider):
    def __init__(self, provider: str = "huggingface"):
        if provider != "huggingface":
            raise ValueError(
                f"Error, HuggingFaceDataProvider was passed `{provider}` as a provider."
            )
        super().__init__(provider)
        try:
            import datasets  # noqa
        except ImportError:
            raise ValueError(
                f"Error, `datasets` must be installed to create a `HuggingFaceDataProvider` object. Please install it using `pip install datasets`."
            )

    def load_datasets(
        self,
        dataset_configs: list[DatasetConfig],
        split: str = "train",
        streaming: bool = True,
    ) -> None:
        logger.info("Loading datasets with HuggingFaceDataProvider now.")
        from datasets import load_dataset

        self.datasets = []  # Prepare to store loaded datasets
        for config in dataset_configs:
            logger.info(
                f"Loading dataset {config.name} with text field {config.text_field} and max entries {config.max_entries}."
            )
            dataset = load_dataset(
                config.name, split=config.split, streaming=streaming
            )
            self.datasets.append((dataset, config))

    def stream_text(
        self,
    ) -> Generator[Optional[Tuple[str, DatasetConfig]], None, None]:
        logger.info("Streaming text with with HuggingFaceDataProvider now.")
        for dataset, config in self.datasets:
            entries_streamed = 0
            for entry in dataset:
                if (
                    config.max_entries is not None
                    and entries_streamed >= config.max_entries
                ):
                    break  # Stop streaming if max_entries is reached

                # Extract text using the specified text field or default to 'text' field
                text_field = config.text_field if config.text_field else "text"
                text = entry[text_field] if text_field in entry else None

                if text:
                    yield text, config
                    entries_streamed += 1
