import pytest

from core.base import ParsingConfig
from core.providers.parsing.unstructured_parsing import (
    UnstructuredParsingProvider,
)


@pytest.fixture
def parsing_config():
    return ParsingConfig()


@pytest.fixture
def unstructured_parsing_provider(parsing_config):
    return UnstructuredParsingProvider(use_api=False, config=parsing_config)
