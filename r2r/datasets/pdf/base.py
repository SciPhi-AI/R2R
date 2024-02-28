import logging
import os
from typing import Generator, Optional, Tuple

from r2r.core import DatasetConfig, DatasetProvider

logger = logging.getLogger(__name__)


class PdfDataReader(DatasetProvider):
    def __init__(self, provider: str = "pdf"):
        if provider != "pdf":
            raise ValueError(
                f"Error, PdfDataReader was passed `{provider}` as a provider."
            )
        super().__init__(provider)
        try:
            from pypdf import PdfReader

            self.PdfReader = PdfReader
            self.pdfs: list[Tuple[PdfReader, DatasetConfig]] = []
        except ImportError:
            raise ValueError(
                "Error, `pypdf` is requried to run `PdfDataReader`. Please install it using `pip install pypdf`."
            )

    def load_datasets(
        self,
        dataset_configs: list[DatasetConfig],
        split: str = "train",
        streaming: bool = True,
    ) -> None:
        logger.info("Loading datasets with HuggingFaceDataProvider now.")
        for config in dataset_configs:
            logger.info(
                f"Loading dataset {config.name} with files {config.data_files}."
            )
            if config.name is None:
                raise ValueError(
                    f"Error, the dataset name must be specified in the `DatasetConfig`."
                )
            if len(config.data_files) == 0:
                raise ValueError(
                    f"Error, the dataset files must be specified in the `DatasetConfig`."
                )
            for file_path in config.data_files:
                if os.path.isfile(file_path):
                    if ".pdf" not in file_path:
                        raise ValueError(
                            f"Error, the file {file_path} is not a pdf file."
                        )
                    pdf = self.PdfReader(file_path)
                    self.pdfs.append((pdf, config))
                elif os.path.isdir(file_path):
                    for root, dirs, files in os.walk(file_path):
                        for file in files:
                            if ".pdf" in file:
                                pdf = self.PdfReader(os.path.join(root, file))
                                self.pdfs.append((pdf, config))

    def stream_text(
        self,
    ) -> Generator[Optional[Tuple[str, DatasetConfig]], None, None]:
        logger.info("Streaming text with with PdfDataReader now.")
        if self.pdfs == []:
            raise ValueError(
                f"Error, no pdfs were loaded with `PdfDataReader`."
            )
        for pdf, config in self.pdfs:
            entries_streamed = 0
            for page in pdf.pages:
                if (
                    config.max_entries is not None
                    and entries_streamed >= config.max_entries
                ):
                    break  # Stop streaming if max_entries is reached

                text = page.extract_text()

                if text:
                    yield text, config
                    entries_streamed += 1
