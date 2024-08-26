import json
from typing import Any, Dict

import click


class JsonParamType(click.ParamType):
    name = "json"

    def convert(self, value, param, ctx) -> Dict[str, Any]:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            self.fail(f"'{value}' is not a valid JSON string", param, ctx)


JSON = JsonParamType()
