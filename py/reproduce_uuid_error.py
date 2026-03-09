import uuid
import re

schema_name = uuid.uuid4()
print(f"Testing with schema_name (type {type(schema_name)}): {schema_name}")

try:
    if not re.match(r"^[a-zA-Z0-9_]+$", schema_name):
        print("Regex match failed (expected for non-string)")
    else:
        print("Regex matched (unexpected for UUID)")
except TypeError as e:
    print(f"Caught expected TypeError in re.match: {e}")

try:
    schema_name.replace('"', "")
    print("Replace succeeded (unexpected for UUID)")
except AttributeError as e:
    print(f"Caught expected AttributeError in replace: {e}")

# Test the fix
fixed_schema_name = str(schema_name).replace('"', "")
print(f"Fixed schema_name: {fixed_schema_name}")
