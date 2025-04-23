from litellm import get_model_info, token_counter
import logging

logger = logging.getLogger(__name__)

def truncate_texts_to_token_limit(texts: list[str], model: str) -> list[str]:
    """
    Truncate texts to fit within the model's token limit.
    """
    try:
        model_info = get_model_info(model=model)
        if not model_info.get("max_input_tokens"):
            return texts  # No truncation needed if no limit specified

        truncated_texts = []
        for text in texts:
            text_tokens = token_counter(model=model, text=text)
            assert model_info["max_input_tokens"]
            if text_tokens > model_info["max_input_tokens"]:
                estimated_chars = (
                    model_info["max_input_tokens"] * 3
                )  # Estimate 3 chars per token
                truncated_text = text[:estimated_chars]
                truncated_texts.append(truncated_text)
                logger.warning(
                    f"Truncated text from {text_tokens} to ~{model_info['max_input_tokens']} tokens"
                )
            else:
                truncated_texts.append(text)

        return truncated_texts
    except Exception as e:
        logger.warning(f"Failed to truncate texts: {str(e)}")
        return texts  # Return original texts if truncation fails
