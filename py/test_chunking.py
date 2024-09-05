from pydantic import BaseModel
from typing import Optional, NotRequired
from typing_extensions import Nullable

class ExampleModel(BaseModel):
    required_field: str
    optional_no_default: NotRequired[Nullable[int]]
    optional_with_default: Optional[int] = 10
    optional_with_none_default: Optional[int] = None

# This will raise a ValidationError because optional_no_default is not provided
# and doesn't have a default value
try:
    instance1 = ExampleModel(required_field="test")
except Exception as e:
    print(f"Error creating instance1: {e}")

# # This works, all optional fields use their default values
# instance2 = ExampleModel(
#     required_field="test",
#     optional_no_default=5
# )
# print(f"instance2: {instance2}")

# # This also works, explicitly setting an optional field to None
# instance3 = ExampleModel(
#     required_field="test",
#     optional_no_default=None,
#     optional_with_default=None
# )
# print(f"instance3: {instance3}")

# # This works too, omitting fields with defaults
# instance4 = ExampleModel(
#     required_field="test",
#     optional_no_default=5
# )
# print(f"instance4: {instance4}")
