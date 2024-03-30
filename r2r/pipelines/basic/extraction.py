from typing import Iterator

from r2r.core import BasicDocument, EntityExtractionPipeline, GenerationConfig
from r2r.pipelines import BasicPromptProvider

class BasicEntityExtractionPipeline(EntityExtractionPipeline):
    BASIC_SYSTEM_PROMPT = "You are a helpful assistant."
    BASIC_TASK_PROMPT = """
    ## Task:
    Extract the named entities from the following text document, and return them in a comma-separated list.

    ## Response:
    """
    def __init__(self, llm, logging_connection=None, *args, **kwargs):
        super().__init__(prompt_provider=BasicPromptProvider(BasicEntityExtractionPipeline.BASIC_SYSTEM_PROMPT, BasicEntityExtractionPipeline.BASIC_TASK_PROMPT), logging_connection=logging_connection, **kwargs)
        self.llm = llm

    def preprocess_text(self, text: str) -> str:
        # Optional - Implement text preprocessing logic here
        return text

    def extract_entities(self, text: str, generation_config: GenerationConfig) -> list[str]:
        # entities = self.com
        self._check_pipeline_initialized()
        messages = [
            {
                "role": "system",
                "content": self.prompt_provider.get_prompt("system_prompt"),

            },
            {
                "role": "user",
                "content": self.prompt_provider.get_prompt("task_prompt"),
            },
        ]
        entities_list =  self.llm.get_completion(text, generation_config)
        if not "," in entities_list:
            entities = []
        else:
            entities = entities_list.split(",")
        return entities
    
    def postprocess_entities(self, entities: list[str]) -> list[str]:
        # Implement entity postprocessing logic here
        return [entity.upper() for entity in entities]

    def run(self, documents: Iterator[BasicDocument]) -> Iterator[BasicDocument]:
        for document in documents:
            preprocessed_text = self.preprocess_text(document.text)
            entities = self.extract_entities(preprocessed_text)
            postprocessed_entities = self.postprocess_entities(entities)
            document.metadata["entities"] = postprocessed_entities
            yield document
