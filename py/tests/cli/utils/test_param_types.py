from unittest.mock import MagicMock

import asyncclick as click
import pytest

from cli.utils.param_types import JSON, JsonParamType


def test_json_param_type_convert_valid_json():
    json_type = JsonParamType()
    result = json_type.convert('{"key": "value"}', None, None)
    assert result == {"key": "value"}


def test_json_param_type_convert_invalid_json():
    json_type = JsonParamType()
    with pytest.raises(click.BadParameter) as excinfo:
        json_type.convert("{invalid json}", None, None)
    assert "is not a valid JSON string" in str(excinfo.value)


def test_json_param_type_convert_dict():
    json_type = JsonParamType()
    input_dict = {"key": "value"}
    result = json_type.convert(input_dict, None, None)
    assert result == input_dict


def test_json_param_type_name():
    json_type = JsonParamType()
    assert json_type.name == "json"


def test_json_global_instance():
    assert isinstance(JSON, JsonParamType)


def test_json_param_type_convert_with_context():
    json_type = JsonParamType()
    mock_ctx = MagicMock()
    mock_param = MagicMock()
    result = json_type.convert('{"key": "value"}', mock_param, mock_ctx)
    assert result == {"key": "value"}


def test_json_param_type_convert_empty_string():
    json_type = JsonParamType()
    with pytest.raises(click.BadParameter) as excinfo:
        json_type.convert("", None, None)
    assert "is not a valid JSON string" in str(excinfo.value)


def test_json_param_type_convert_none():
    json_type = JsonParamType()
    result = json_type.convert(None, None, None)
    assert result is None


def test_json_param_type_convert_complex_json():
    json_type = JsonParamType()
    complex_json = (
        '{"key1": "value1", "key2": [1, 2, 3], "key3": {"nested": true}}'
    )
    result = json_type.convert(complex_json, None, None)
    assert result == {
        "key1": "value1",
        "key2": [1, 2, 3],
        "key3": {"nested": True},
    }
