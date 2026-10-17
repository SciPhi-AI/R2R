from copy import deepcopy

import pytest

from shared.abstractions.llm import GenerationConfig


@pytest.fixture(autouse=True)
def restore_generation_defaults():
    saved = deepcopy(GenerationConfig._defaults)
    yield
    GenerationConfig._defaults = saved


@pytest.mark.parametrize(
    "field, value",
    [
        ("reasoning_effort", "none"),
        ("extended_thinking", True),
        ("thinking_budget", 2048),
        ("max_tokens_to_sample", 4096),
    ],
)
def test_set_default_applies_to_new_instances(field, value):
    """Values from `[completion.generation_config]` are applied through
    `GenerationConfig.set_default`; every field must pick them up."""
    GenerationConfig.set_default(**{field: value})

    assert getattr(GenerationConfig(), field) == value


def test_explicit_value_overrides_default():
    GenerationConfig.set_default(reasoning_effort="none")

    assert GenerationConfig(reasoning_effort="high").reasoning_effort == "high"
