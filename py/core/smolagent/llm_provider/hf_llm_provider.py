import logging

from smolagents import Model

logger = logging.getLogger(__name__)


def fetch_hf_inference_from_model(model_name: str) -> Model:
    logger.debug(f"Fetching HF inference from model: {model_name}")
    if "gpt" in model_name:
        from smolagents import OpenAIServerModel

        # Initialize the model with our reverse proxy
        # remove openai/ prefix if there is one
        model_id = model_name.replace("openai/", "")
        return OpenAIServerModel(
            model_id=model_id,
        )
    else:
        raise ValueError(f"Model {model_name} is not supported")
