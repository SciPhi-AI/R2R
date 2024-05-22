import pytest

from r2r import GenerationConfig, LLMConfig
from r2r.llms import LiteLLM


@pytest.fixture
def lite_llm():
    config = LLMConfig(provider="litellm")
    return LiteLLM(config)


@pytest.mark.parametrize("llm_fixture", ["lite_llm"])
def test_get_completion_ollama(request, llm_fixture):
    llm = request.getfixturevalue(llm_fixture)

    messages = [
        {
            "role": "user",
            "content": "This is a test, return only the word `True`",
        }
    ]
    generation_config = GenerationConfig(
        model="ollama/llama2",
        temperature=0.0,
        top_p=0.9,
        max_tokens_to_sample=50,
        stream=False,
    )

    completion = llm.get_completion(messages, generation_config)
    # assert isinstance(completion, LLMChatCompletion)
    assert completion.choices[0].message.role == "assistant"
    assert completion.choices[0].message.content.strip() == "True"


@pytest.mark.parametrize("llm_fixture", ["lite_llm"])
def test_get_completion_openai(request, llm_fixture):
    llm = request.getfixturevalue(llm_fixture)

    messages = [
        {
            "role": "user",
            "content": "This is a test, return only the word `True`",
        }
    ]
    generation_config = GenerationConfig(
        model="gpt-3.5-turbo",
        temperature=0.0,
        top_p=0.9,
        max_tokens_to_sample=50,
        stream=False,
    )

    completion = llm.get_completion(messages, generation_config)
    # assert isinstance(completion, LLMChatCompletion)
    assert completion.choices[0].message.role == "assistant"
    assert completion.choices[0].message.content.strip() == "True"
