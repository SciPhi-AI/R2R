from abc import abstractmethod
from typing import Iterator, Optional

from ..providers.prompt import PromptProvider
from ..providers.llm import LLMProvider
from ..providers.logging import LoggingDatabaseConnection, log_execution_to_db
from r2r.core import BasicDocument, GenerationConfig
from r2r.pipelines import Pipeline

class EntityExtractionPipeline(Pipeline):
    def __init__(
        self,
        llm: LLMProvider,
        prompt_provider: PromptProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.llm = llm
        self.prompt_provider = prompt_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    @abstractmethod
    def preprocess_text(self, text: str) -> str:
        pass

    @abstractmethod
    def extract_entities(self, text: str, generation_config: GenerationConfig) -> list[str]:
        pass

    @abstractmethod
    def postprocess_entities(self, entities: list[str]) -> list[str]:
        pass

    @abstractmethod
    def run(self, documents: Iterator[BasicDocument]) -> Iterator[BasicDocument]:
        pass
