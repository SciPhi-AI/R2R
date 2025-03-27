import json
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# --- Constants ---

class FilterOperator:
    # Comparison
    EQ = "$eq"
    NE = "$ne"
    LT = "$lt"
    LTE = "$lte"
    GT = "$gt"
    GTE = "$gte"
    # Array / Set Membership
    IN = "$in"
    NIN = "$nin"
    # String Matching
    LIKE = "$like"  # Case-sensitive
    ILIKE = "$ilike" # Case-insensitive
    # Array Specific (for native PostgreSQL arrays like UUID[])
    OVERLAP = "$overlap"       # Check if arrays share any common elements (uses &&)
    ARRAY_CONTAINS = "$contains" # Check if array contains ALL specified elements (uses @>)
    # JSONB Specific
    JSON_CONTAINS = "$json_contains" # Check if JSONB contains the specified JSONB structure/value (uses @>)
    # Logical
    AND = "$and"
    OR = "$or"

    # Sets for easier checking
    SCALAR_OPS = {EQ, NE, LT, LTE, GT, GTE, LIKE, ILIKE}
    LIST_INPUT_OPS = {IN, NIN, OVERLAP, ARRAY_CONTAINS} # Ops requiring a list as input value
    LOGICAL_OPS = {AND, OR}
    # Note: JSON_CONTAINS can take various input types

# Default column names assumed to be top-level unless specified otherwise
DEFAULT_TOP_LEVEL_COLUMNS = {
    "id",
    "document_id",
    "owner_id",
    "collection_ids", # Special handling as UUID[]
    "created_at",
    "updated_at",
    "status",
    "text", # For potential direct filtering, though FTS is usually better
    "type", # Example if you have a type column
    # Add other known top-level, non-JSONB columns here
}

# --- Error Class ---

class FilterError(ValueError):
    """Custom error for filter processing issues."""
    pass

# --- Helper for Parameter Management ---

class ParamHelper:
    """Manages SQL parameters and positional placeholder generation."""
    def __init__(self, initial_params: Optional[List[Any]] = None):
        self.params: List[Any] = initial_params or []
        self.index: int = len(self.params) + 1

    def add(self, value: Any) -> str:
        """Adds a parameter and returns its placeholder (e.g., '$1')."""
        self.params.append(value)
        placeholder = f"${self.index}"
        self.index += 1
        return placeholder

# --- Core Filter Processing Logic ---

def _process_filter_dict(
    filter_dict: Dict[str, Any],
    param_helper: ParamHelper,
    top_level_columns: Set[str],
    json_column: str,
) -> str:
    """Recursively processes a filter dictionary node."""
    if not filter_dict:
        return "TRUE"

    conditions = []

    for key, value in filter_dict.items():
        # Logical Operators
        if key == FilterOperator.AND:
            if not isinstance(value, list):
                raise FilterError(f"'{FilterOperator.AND}' value must be a list of filter dictionaries.")
            if not value:
                # An empty $and is typically true (vacuously)
                conditions.append("TRUE")
                continue
            sub_conditions = [
                f"({_process_filter_dict(item, param_helper, top_level_columns, json_column)})"
                for item in value if isinstance(item, dict)
            ]
            if sub_conditions:
                conditions.append(" AND ".join(sub_conditions))

        elif key == FilterOperator.OR:
            if not isinstance(value, list):
                raise FilterError(f"'{FilterOperator.OR}' value must be a list of filter dictionaries.")
            if not value:
                 # An empty $or is typically false
                conditions.append("FALSE")
                continue
            sub_conditions = [
                f"({_process_filter_dict(item, param_helper, top_level_columns, json_column)})"
                for item in value if isinstance(item, dict)
            ]
            if sub_conditions:
                conditions.append(" OR ".join(sub_conditions))

        # Field Conditions
        else:
            field = key
            condition_spec = value
            sql_condition = _process_field_condition(
                field, condition_spec, param_helper, top_level_columns, json_column
            )
            conditions.append(sql_condition)

    if not conditions:
        return "TRUE" # Should generally not happen if filter_dict is not empty

    # Multiple conditions at the same level are implicitly ANDed
    return " AND ".join(c for c in conditions if c != "TRUE") or "TRUE"


def _process_field_condition(
    field: str,
    condition_spec: Any,
    param_helper: ParamHelper,
    top_level_columns: Set[str],
    json_column: str,
) -> str:
    """Processes a condition for a specific field."""

    # Determine field type
    is_collection_ids = (field == "collection_ids")
    # Shorthand: 'collection_id' filter operates on 'collection_ids' array
    is_collection_id_shorthand = (field == "collection_id")
    is_top_level = field in top_level_columns
    is_metadata = not is_top_level and not is_collection_id_shorthand # Assume non-top-level is metadata

    if is_collection_id_shorthand:
        # Treat collection_id as a filter on the collection_ids array
        # Usually implies checking for the presence of that single ID.
        # Map to $overlap for common use case.
        if isinstance(condition_spec, dict) and len(condition_spec) == 1:
             op, value = next(iter(condition_spec.items()))
             # Allow specific ops if needed, but default simple value to overlap
             if op == FilterOperator.EQ: # Map $eq on shorthand to overlap check
                 return _build_collection_ids_condition(field, FilterOperator.OVERLAP, [value], param_helper)
             elif op == FilterOperator.NE: # Map $ne on shorthand to NOT overlap check
                 return _build_collection_ids_condition(field, FilterOperator.NIN, [value], param_helper)
             else: # Allow other ops like $in, $nin directly if user specifies the operator
                 return _build_collection_ids_condition(field, op, value, param_helper)
        elif isinstance(condition_spec, (str, uuid.UUID)):
            # Shorthand: collection_id: "some-uuid" means collection_ids overlaps with ["some-uuid"]
            return _build_collection_ids_condition(field, FilterOperator.OVERLAP, [condition_spec], param_helper)
        else:
            raise FilterError(f"Invalid condition for shorthand '{field}'. Expected UUID string or {{op: value}} dict.")

    elif is_collection_ids:
        # Direct operations on the collection_ids UUID[] field
        if isinstance(condition_spec, dict) and len(condition_spec) == 1:
            op, value = next(iter(condition_spec.items()))
            return _build_collection_ids_condition(field, op, value, param_helper)
        elif isinstance(condition_spec, list):
             # Shorthand: collection_ids: ["id1", "id2"] implies overlap
             return _build_collection_ids_condition(field, FilterOperator.OVERLAP, condition_spec, param_helper)
        else:
            raise FilterError(f"Invalid condition for '{field}'. Expected {{op: value}} dict or list of UUIDs.")

    elif is_metadata:
        # Operations on the JSONB metadata field
        if isinstance(condition_spec, dict) and len(condition_spec) == 1:
             # Check if the key is a known operator or part of a nested path
            op_or_path, value = next(iter(condition_spec.items()))
            if op_or_path.startswith("$"): # It's an operator
                return _build_metadata_condition(field, op_or_path, value, param_helper, json_column)
            else: # It's likely a nested path, treat as shorthand for equality
                 nested_field = f"{field}.{op_or_path}"
                 return _build_metadata_condition(nested_field, FilterOperator.EQ, value, param_helper, json_column)
        else:
            # Shorthand: metadata_field: value means equality
            return _build_metadata_condition(field, FilterOperator.EQ, condition_spec, param_helper, json_column)

    elif is_top_level:
         # Operations on standard, top-level SQL columns
        if isinstance(condition_spec, dict) and len(condition_spec) == 1:
            op, value = next(iter(condition_spec.items()))
            # Ensure the key is a valid operator
            if not op.startswith("$"):
                 raise FilterError(f"Invalid operator '{op}' for field '{field}'. Operators must start with '$'.")
            return _build_standard_column_condition(field, op, value, param_helper)
        else:
            # Shorthand: top_level_field: value means equality
            return _build_standard_column_condition(field, FilterOperator.EQ, condition_spec, param_helper)
    else:
         # Should not be reached if logic is correct
         raise FilterError(f"Could not determine filter type for field '{field}'.")


# --- Builder Functions for Specific Field Types ---

def _build_standard_column_condition(
    field: str, op: str, value: Any, param_helper: ParamHelper
) -> str:
    """Builds SQL condition for standard (non-array, non-JSONB) columns."""

    # Handle NULL comparisons
    if value is None:
        if op == FilterOperator.EQ:
            return f"{field} IS NULL"
        elif op == FilterOperator.NE:
            return f"{field} IS NOT NULL"
        else:
            # Other operators typically don't make sense with NULL comparison in SQL
            # and often result in NULL (effectively false in WHERE)
            return "FALSE" # Or raise error? Let's return FALSE.

    # Standard comparisons
    if op == FilterOperator.EQ:
        placeholder = param_helper.add(value)
        return f"{field} = {placeholder}"
    elif op == FilterOperator.NE:
        placeholder = param_helper.add(value)
        return f"{field} != {placeholder}"
    elif op == FilterOperator.GT:
        placeholder = param_helper.add(value)
        return f"{field} > {placeholder}"
    elif op == FilterOperator.GTE:
        placeholder = param_helper.add(value)
        return f"{field} >= {placeholder}"
    elif op == FilterOperator.LT:
        placeholder = param_helper.add(value)
        return f"{field} < {placeholder}"
    elif op == FilterOperator.LTE:
        placeholder = param_helper.add(value)
        return f"{field} <= {placeholder}"

    # String comparisons
    elif op == FilterOperator.LIKE:
         if not isinstance(value, str):
             raise FilterError(f"'{FilterOperator.LIKE}' requires a string value for field '{field}'.")
         placeholder = param_helper.add(value) # Assume user includes wildcards if needed
         return f"{field} LIKE {placeholder}"
    elif op == FilterOperator.ILIKE:
         if not isinstance(value, str):
             raise FilterError(f"'{FilterOperator.ILIKE}' requires a string value for field '{field}'.")
         placeholder = param_helper.add(value) # Assume user includes wildcards if needed
         return f"{field} ILIKE {placeholder}"

    # IN / NOT IN
    elif op == FilterOperator.IN:
        if not isinstance(value, list):
            raise FilterError(f"'{FilterOperator.IN}' requires a list value for field '{field}'.")
        if not value:
            return "FALSE" # IN empty list is always false
        placeholders = [param_helper.add(item) for item in value]
        return f"{field} IN ({', '.join(placeholders)})"
    elif op == FilterOperator.NIN:
        if not isinstance(value, list):
            raise FilterError(f"'{FilterOperator.NIN}' requires a list value for field '{field}'.")
        if not value:
            return "TRUE" # NOT IN empty list is always true
        placeholders = [param_helper.add(item) for item in value]
        return f"{field} NOT IN ({', '.join(placeholders)})"

    else:
        raise FilterError(f"Unsupported operator '{op}' for standard column '{field}'.")


def _build_collection_ids_condition(
    field_name: str, # Can be 'collection_ids' or 'collection_id' (shorthand)
    op: str,
    value: Any,
    param_helper: ParamHelper
) -> str:
    """Builds SQL condition for the 'collection_ids' UUID[] array column."""
    target_column = "collection_ids" # Always operate on the actual column

    # --- Operators requiring a list of UUIDs ---
    if op in [FilterOperator.OVERLAP, FilterOperator.ARRAY_CONTAINS, FilterOperator.IN, FilterOperator.NIN]:
        if not isinstance(value, list):
            # Allow single value for shorthand ops triggered via collection_id: "uuid"
            if field_name == "collection_id" and isinstance(value, (str, uuid.UUID)):
                value = [value]
            else:
                 raise FilterError(f"Operator '{op}' on '{target_column}' requires a list of UUID strings.")

        if not value: # Empty list handling
            if op == FilterOperator.OVERLAP or op == FilterOperator.IN: return "FALSE"
            if op == FilterOperator.ARRAY_CONTAINS: return "TRUE" # Contains all elements of an empty set is true
            if op == FilterOperator.NIN: return "TRUE"

        # Validate and convert values to UUID strings for the ARRAY constructor
        try:
            uuid_strings = [str(uuid.UUID(str(item))) for item in value]
        except (ValueError, TypeError) as e:
            raise FilterError(f"Invalid UUID format in list for '{target_column}' filter: {e}")

        # Build ARRAY[...]::uuid[] literal with individual parameters
        placeholders = [param_helper.add(uid_str) for uid_str in uuid_strings]
        array_literal = f"ARRAY[{', '.join(placeholders)}]::uuid[]"

        if op == FilterOperator.OVERLAP or op == FilterOperator.IN: # IN on array means overlap
            return f"{target_column} && {array_literal}"
        elif op == FilterOperator.ARRAY_CONTAINS: # Check if target_column contains ALL elements in value
             return f"{target_column} @> {array_literal}"
        elif op == FilterOperator.NIN: # Check if target_column contains NONE of the elements in value
             return f"NOT ({target_column} && {array_literal})"

    # --- Operators requiring a single UUID ---
    elif op == FilterOperator.EQ: # Check if array IS EXACTLY this single element array (rare)
         if isinstance(value, (str, uuid.UUID)):
             try:
                 uuid_str = str(uuid.UUID(str(value)))
                 placeholder = param_helper.add(uuid_str)
                 return f"{target_column} = ARRAY[{placeholder}]::uuid[]"
             except (ValueError, TypeError) as e:
                 raise FilterError(f"Invalid UUID format for '{op}' on '{target_column}': {e}")
         else:
             raise FilterError(f"Operator '{op}' on '{target_column}' requires a single UUID string value.")

    elif op == FilterOperator.NE: # Check if array IS NOT EXACTLY this single element array (rare)
         if isinstance(value, (str, uuid.UUID)):
             try:
                 uuid_str = str(uuid.UUID(str(value)))
                 placeholder = param_helper.add(uuid_str)
                 return f"{target_column} != ARRAY[{placeholder}]::uuid[]"
             except (ValueError, TypeError) as e:
                 raise FilterError(f"Invalid UUID format for '{op}' on '{target_column}': {e}")
         else:
             raise FilterError(f"Operator '{op}' on '{target_column}' requires a single UUID string value.")

    else:
        raise FilterError(f"Unsupported operator '{op}' for array column '{target_column}'.")

def _build_metadata_condition(
    field_path: str, op: str, value: Any, param_helper: ParamHelper, json_column: str
) -> str:
    """Builds SQL condition for a potentially nested field within a JSONB column."""

    # Build JSON path expression (using ->> for text extraction by default)
    path_parts = field_path.split('.')
    if len(path_parts) == 1:
        # Use ->> to extract as text for comparison, unless it's a JSONB op
        json_accessor = f"{json_column}->>'{path_parts[0]}'" if op != FilterOperator.JSON_CONTAINS else f"{json_column}->'{path_parts[0]}'"
    else:
        # Use #>> for nested text extraction, #> for nested JSONB extraction
        path_literal = "{" + ",".join(path_parts) + "}"
        json_accessor = f"{json_column}#>>'{path_literal}'" if op != FilterOperator.JSON_CONTAINS else f"{json_column}#>'{path_literal}'"

    # Handle NULL comparisons against JSONB presence/value
    if value is None:
         # Check if the key/path exists and its value is JSON null
        if op == FilterOperator.EQ:
            # Need to check existence AND value being null
            if len(path_parts) == 1:
                exists_check = f"{json_column} ? '{path_parts[0]}'"
            else:
                 # jsonb_path_exists might be needed for deep paths, or use #> IS NULL
                 path_literal = "{" + ",".join(path_parts) + "}"
                 exists_check = f"{json_column}#>'{path_literal}' IS NOT NULL" # Path exists...

            # Check if value at path is JSON null
            value_is_null_check = f"({json_accessor})::jsonb = 'null'::jsonb"

            return f"({exists_check} AND {value_is_null_check})" # Path exists AND value is JSON null

        elif op == FilterOperator.NE:
             # Check if path *doesn't* exist OR if it exists and value is NOT JSON null
             if len(path_parts) == 1:
                 exists_check = f"{json_column} ? '{path_parts[0]}'"
             else:
                  path_literal = "{" + ",".join(path_parts) + "}"
                  exists_check = f"{json_column}#>'{path_literal}' IS NOT NULL"

             value_is_not_null_check = f"({json_accessor})::jsonb != 'null'::jsonb"

             return f"(NOT {exists_check} OR ({exists_check} AND {value_is_not_null_check}))" # Path missing OR (Path exists AND value not JSON null)
        else:
            return "FALSE" # Other ops with null usually don't work as expected

    # --- JSONB Contains ---
    if op == FilterOperator.JSON_CONTAINS:
        try:
            # Value needs to be valid JSON
            json_value_str = json.dumps(value)
            placeholder = param_helper.add(json_value_str)
            # Use the JSONB containment operator @>
            # Note: json_accessor uses '->' or '#>' here
            return f"{json_accessor} @> {placeholder}::jsonb"
        except TypeError as e:
            raise FilterError(f"Value for '{FilterOperator.JSON_CONTAINS}' on '{field_path}' must be JSON serializable: {e}")

    # --- Standard comparisons (operating on text extraction ->> or #>>) ---
    sql_op_map = {
        FilterOperator.EQ: "=", FilterOperator.NE: "!=",
        FilterOperator.LT: "<", FilterOperator.LTE: "<=",
        FilterOperator.GT: ">", FilterOperator.GTE: ">=",
    }

    if op in sql_op_map:
        sql_operator = sql_op_map[op]
        # Determine appropriate casting based on value type
        if isinstance(value, bool):
            placeholder = param_helper.add(value)
            return f"({json_accessor})::boolean {sql_operator} {placeholder}"
        elif isinstance(value, (int, float)):
            placeholder = param_helper.add(value)
            # Use numeric for broader compatibility than int/float
            return f"({json_accessor})::numeric {sql_operator} {placeholder}"
        elif isinstance(value, str):
             placeholder = param_helper.add(value)
             # No cast needed for text vs text
             return f"{json_accessor} {sql_operator} {placeholder}"
        else:
            # Fallback to text comparison for other types
            placeholder = param_helper.add(str(value))
            return f"{json_accessor} {sql_operator} {placeholder}"

    # --- String Like ---
    elif op == FilterOperator.LIKE:
        if not isinstance(value, str):
            raise FilterError(f"'{FilterOperator.LIKE}' requires a string value for metadata field '{field_path}'.")
        placeholder = param_helper.add(value)
        return f"{json_accessor} LIKE {placeholder}"
    elif op == FilterOperator.ILIKE:
        if not isinstance(value, str):
            raise FilterError(f"'{FilterOperator.ILIKE}' requires a string value for metadata field '{field_path}'.")
        placeholder = param_helper.add(value)
        return f"{json_accessor} ILIKE {placeholder}"

    # --- IN / NOT IN (operating on text extraction) ---
    elif op == FilterOperator.IN:
        if not isinstance(value, list):
             raise FilterError(f"'{FilterOperator.IN}' requires a list value for metadata field '{field_path}'.")
        if not value: return "FALSE"
        # Assume comparison against text representation
        placeholders = [param_helper.add(str(item)) for item in value]
        return f"{json_accessor} IN ({', '.join(placeholders)})"

    elif op == FilterOperator.NIN:
         if not isinstance(value, list):
             raise FilterError(f"'{FilterOperator.NIN}' requires a list value for metadata field '{field_path}'.")
         if not value: return "TRUE"
         placeholders = [param_helper.add(str(item)) for item in value]
         return f"{json_accessor} NOT IN ({', '.join(placeholders)})"

    else:
        raise FilterError(f"Unsupported operator '{op}' for metadata field '{field_path}'.")


# --- Public API Function ---

def apply_filters(
    filters: Dict[str, Any],
    param_list: Optional[List[Any]] = None, # Pass list to accumulate params
    top_level_columns: Optional[Union[Set[str], List[str]]] = None,
    json_column: str = "metadata",
    mode: str = "where_clause", # Controls output format
) -> Tuple[str, List[Any]]:
    """
    Applies a dictionary of filters to generate SQL conditions and parameters.

    Args:
        filters: Dictionary representing the filter query (MongoDB-like syntax).
        param_list: An optional existing list to append parameters to.
                    If None, a new list is created.
        top_level_columns: Optional set or list of column names considered top-level
                           (not part of the json_column). Defaults are used if None.
        json_column: The name of the column storing JSONB data (default: 'metadata').
        mode: 'where_clause' returns "WHERE condition", 'condition_only' returns "condition".

    Returns:
        Tuple containing:
            - The generated SQL condition string (potentially prefixed with 'WHERE ').
            - The list of parameters collected.

    Raises:
        FilterError: If the filter structure or operators are invalid.
    """
    if param_list is None:
        param_list = []

    param_helper = ParamHelper(initial_params=param_list)

    # Initialize top_level_columns with defaults if not provided
    if top_level_columns is None:
        processed_top_level_columns = DEFAULT_TOP_LEVEL_COLUMNS.copy()
    elif isinstance(top_level_columns, list):
        processed_top_level_columns = set(top_level_columns)
    elif isinstance(top_level_columns, set):
         processed_top_level_columns = top_level_columns.copy()
    else:
        raise TypeError("top_level_columns must be a Set, List, or None.")

    # Ensure json_column itself is not treated as a filterable top-level column directly
    processed_top_level_columns.discard(json_column)

    # Handle empty filter case
    if not filters:
        condition = "TRUE"
    else:
        try:
            condition = _process_filter_dict(
                filters, param_helper, processed_top_level_columns, json_column
            )
            # If processing resulted in an empty condition string, default to TRUE
            if not condition:
                condition = "TRUE"
        except FilterError as e:
            # Re-raise with context if needed, or just let it propagate
            raise e
        except Exception as e:
            # Catch unexpected errors during processing
            raise FilterError(f"Unexpected error processing filters: {e}") from e


    if mode == "where_clause":
        # Avoid adding WHERE if the condition is effectively empty or always true/false
        if condition == "TRUE":
            # Return empty string for WHERE clause if filter is vacuous
             return "", param_helper.params
        elif condition == "FALSE":
             # If the condition is always false, indicate it clearly
             return "WHERE FALSE", param_helper.params
        else:
             return f"WHERE {condition}", param_helper.params
    elif mode == "condition_only":
        return condition, param_helper.params
    else:
        raise FilterError(f"Unsupported filter mode: {mode}. Choose 'where_clause' or 'condition_only'.")
        
        
# import json
# import uuid
# from typing import Any, Optional

# # Using lowercase list, dict, etc. to comply with pre-commit check
# # and maintain backward compatibility

# # List of column variables
# COLUMN_VARS = [
#     "id",
#     "document_id",
#     "owner_id",
#     "collection_ids",
# ]

# DEFAULT_TOP_LEVEL_COLUMNS = {
#     "id",
#     "parent_id",
#     "collection_id",
#     "collection_ids",
#     "embedding_id",
#     "created_at",
#     "updated_at",
#     "document_id",
#     "owner_id",
#     "type",
#     "status",
# }


# class FilterError(Exception):
#     pass


# class FilterOperator:
#     EQ = "$eq"
#     NE = "$ne"
#     LT = "$lt"
#     LTE = "$lte"
#     GT = "$gt"
#     GTE = "$gte"
#     IN = "$in"
#     NIN = "$nin"
#     LIKE = "$like"
#     ILIKE = "$ilike"
#     CONTAINS = "$contains"
#     ARRAY_CONTAINS = "$array_contains"
#     AND = "$and"
#     OR = "$or"
#     OVERLAP = "$overlap"

#     SCALAR_OPS = {EQ, NE, LT, LTE, GT, GTE, LIKE, ILIKE}
#     ARRAY_OPS = {IN, NIN, OVERLAP}
#     JSON_OPS = {CONTAINS, ARRAY_CONTAINS}
#     LOGICAL_OPS = {AND, OR}


# def _process_logical_operator(
#     op: str,
#     conditions: list[dict],
#     params: list[Any],
#     top_level_columns: set[str],
#     json_column: str,
# ) -> tuple[str, list[Any]]:
#     """Process a logical operator ($and or $or) into SQL."""
#     if not isinstance(conditions, list):
#         raise FilterError(f"{op} value must be a list")

#     parts = []
#     for item in conditions:
#         if not isinstance(item, dict):
#             raise FilterError("Invalid filter format")

#         sql, params = _process_filter_dict(
#             item, params, top_level_columns, json_column
#         )
#         parts.append(f"({sql})")

#     if not parts:  # Handle empty conditions list
#         if op == FilterOperator.AND:
#             return "TRUE", params
#         else:  # OR
#             return "FALSE", params

#     logical_connector = " AND " if op == FilterOperator.AND else " OR "
#     return logical_connector.join(parts), params


# def _process_field_condition(
#     field: str,
#     condition: Any,
#     params: list[Any],
#     top_level_columns: set[str],
#     json_column: str,
# ) -> tuple[str, list[Any]]:
#     """Process a field condition."""
#     # Handle special fields first
#     if field == "collection_id":
#         if not isinstance(condition, dict):
#             # Direct value - shorthand for equality
#             return _build_collection_id_condition(
#                 FilterOperator.EQ, condition, params
#             )
#         op, value = next(iter(condition.items()))
#         return _build_collection_id_condition(op, value, params)

#     elif field == "collection_ids":
#         if not isinstance(condition, dict):
#             # Direct value - shorthand for equality
#             return _build_collection_ids_condition(
#                 FilterOperator.EQ, condition, params
#             )
#         op, value = next(iter(condition.items()))
#         return _build_collection_ids_condition(op, value, params)

#     elif field == "parent_id":
#         if not isinstance(condition, dict):
#             # Direct value - shorthand for equality
#             return _build_parent_id_condition(
#                 FilterOperator.EQ, condition, params
#             )
#         op, value = next(iter(condition.items()))
#         return _build_parent_id_condition(op, value, params)

#     # Determine if this is a metadata field or standard column
#     field_is_metadata = field not in top_level_columns

#     # Handle direct value (shorthand for equality)
#     if not isinstance(condition, dict):
#         if field_is_metadata:
#             return _build_metadata_condition(
#                 field, FilterOperator.EQ, condition, params, json_column
#             )
#         else:
#             return _build_column_condition(
#                 field, FilterOperator.EQ, condition, params
#             )

#     # Handle operator-based condition
#     if len(condition) != 1:
#         raise FilterError(f"Invalid condition format for field {field}")

#     op, value = next(iter(condition.items()))

#     if field_is_metadata:
#         return _build_metadata_condition(field, op, value, params, json_column)
#     else:
#         return _build_column_condition(field, op, value, params)


# def _process_filter_dict(
#     filter_dict: dict,
#     params: list[Any],
#     top_level_columns: set[str],
#     json_column: str,
# ) -> tuple[str, list[Any]]:
#     """Process a filter dictionary into SQL conditions."""
#     if not filter_dict:
#         return "TRUE", params

#     # Check for logical operators
#     logical_conditions = []
#     field_conditions = []

#     for key, value in filter_dict.items():
#         # Handle logical operators
#         if key == FilterOperator.AND:
#             if not isinstance(value, list):
#                 raise FilterError("$and requires a list of conditions")

#             condition, params = _process_logical_operator(
#                 key, value, params, top_level_columns, json_column
#             )
#             if condition:
#                 logical_conditions.append(condition)

#         elif key == FilterOperator.OR:
#             if not isinstance(value, list):
#                 raise FilterError("$or requires a list of conditions")

#             condition, params = _process_logical_operator(
#                 key, value, params, top_level_columns, json_column
#             )
#             if condition:
#                 logical_conditions.append(condition)

#         # Handle field conditions
#         else:
#             condition, params = _process_field_condition(
#                 key, value, params, top_level_columns, json_column
#             )
#             if condition:
#                 field_conditions.append(condition)

#     # Combine conditions
#     all_conditions = logical_conditions + field_conditions

#     if not all_conditions:
#         return "TRUE", params

#     # Multiple field conditions are implicitly AND-ed together
#     if len(all_conditions) > 1:
#         return " AND ".join(all_conditions), params
#     else:
#         return all_conditions[0], params


# def _build_operator_condition(
#     field: str,
#     op: str,
#     value: Any,
#     params: list[Any],
#     top_level_columns: set[str],
#     json_column: str,
# ) -> tuple[str, list[Any]]:
#     """Build SQL for an operator condition with proper type handling."""
#     # Special case for collection_id field
#     if field == "collection_id":
#         return _build_collection_id_condition(op, value, params)

#     # Special case for parent_id
#     if field == "parent_id":
#         return _build_parent_id_condition(op, value, params)

#     # Decide if it's a top-level column or metadata field
#     field_is_metadata = field not in top_level_columns

#     if field_is_metadata:
#         return _build_metadata_condition(field, op, value, params, json_column)
#     elif field == "collection_ids":
#         return _build_collection_ids_condition(op, value, params)
#     else:
#         return _build_column_condition(field, op, value, params)


# def _build_parent_id_condition(
#     op: str, value: Any, params: list[Any]
# ) -> tuple[str, list[Any]]:
#     """Build SQL condition for parent_id field."""
#     if op == FilterOperator.EQ:
#         if value is None:
#             return "parent_id IS NULL", params

#         # Handle direct value case
#         # Convert to string in case it's a UUID object
#         value_str = str(value)

#         # Try to validate as UUID but don't raise error if it's not valid
#         try:
#             uuid.UUID(value_str)
#             params.append(value_str)
#             return "parent_id = ?", params
#         except (ValueError, TypeError):
#             # For non-UUID strings, use text comparison
#             params.append(value_str)
#             return "parent_id = ?", params

#     elif op == FilterOperator.NE:
#         if value is None:
#             return "parent_id IS NOT NULL", params

#         # Handle direct value case
#         # Convert to string in case it's a UUID object
#         value_str = str(value)

#         # Try to validate as UUID but don't raise error if it's not valid
#         try:
#             uuid.UUID(value_str)
#             params.append(value_str)
#             return "parent_id != ?", params
#         except (ValueError, TypeError):
#             # For non-UUID strings, use text comparison
#             params.append(value_str)
#             return "parent_id != ?", params

#     elif op == FilterOperator.IN:
#         if not isinstance(value, list):
#             raise FilterError("$in for parent_id expects a list of strings")

#         if not value:
#             # Empty list should produce FALSE
#             return "FALSE", params

#         # Check if all values are valid UUIDs
#         try:
#             all_uuids = True
#             uuids = []
#             for v in value:
#                 if not isinstance(v, str) and not isinstance(v, uuid.UUID):
#                     raise FilterError(
#                         "$in for parent_id expects string values"
#                     )
#                 v_str = str(v)
#                 try:
#                     uuids.append(str(uuid.UUID(v_str)))
#                 except (ValueError, TypeError):
#                     all_uuids = False
#                     break

#             if all_uuids:
#                 params.append(uuids)
#                 return "parent_id = ANY(?)", params
#             else:
#                 # For non-UUID strings, use text array
#                 params.append([str(v) for v in value])
#                 return "parent_id = ANY(?)", params
#         except Exception as e:
#             # Fallback for any unexpected errors
#             params.append([str(v) for v in value])
#             return "parent_id = ANY(?)", params

#     elif op == FilterOperator.NIN:
#         if not isinstance(value, list):
#             raise FilterError("$nin for parent_id expects a list of strings")

#         if not value:
#             # Empty list should produce TRUE (nothing to exclude)
#             return "TRUE", params

#         # Check if all values are valid UUIDs
#         try:
#             all_uuids = True
#             uuids = []
#             for v in value:
#                 if not isinstance(v, str) and not isinstance(v, uuid.UUID):
#                     raise FilterError(
#                         "$nin for parent_id expects string values"
#                     )
#                 v_str = str(v)
#                 try:
#                     uuids.append(str(uuid.UUID(v_str)))
#                 except (ValueError, TypeError):
#                     all_uuids = False
#                     break

#             if all_uuids:
#                 params.append(uuids)
#                 return "parent_id != ALL(?)", params
#             else:
#                 # For non-UUID strings, use text array
#                 params.append([str(v) for v in value])
#                 return "parent_id != ALL(?)", params
#         except Exception:
#             # Fallback for any unexpected errors
#             params.append([str(v) for v in value])
#             return "parent_id != ALL(?)", params

#     else:
#         raise FilterError(f"Unsupported operator {op} for parent_id")


# def _build_collection_id_condition(
#     op: str, value: Any, params: list[Any]
# ) -> tuple[str, list[Any]]:
#     """Build SQL condition for collection_id field (shorthand for collection_ids array)."""
#     if op == FilterOperator.EQ:
#         if not isinstance(value, str) and not isinstance(value, uuid.UUID):
#             raise FilterError("$eq for collection_id expects a string value")

#         value_str = str(value)

#         # Try to validate as UUID but don't raise error if it's not valid
#         try:
#             uuid.UUID(value_str)
#             params.append(value_str)
#             return "collection_ids && ARRAY[?]::uuid", params
#         except (ValueError, TypeError):
#             # For testing with non-UUID strings
#             params.append(value_str)
#             return "collection_ids && ARRAY[?]", params

#     elif op == FilterOperator.NE:
#         if not isinstance(value, str) and not isinstance(value, uuid.UUID):
#             raise FilterError("$ne for collection_id expects a string value")

#         value_str = str(value)

#         # Try to validate as UUID but don't raise error if it's not valid
#         try:
#             uuid.UUID(value_str)
#             params.append(value_str)
#             return "NOT (collection_ids && ARRAY[?]::uuid)", params
#         except (ValueError, TypeError):
#             # For testing with non-UUID strings
#             params.append(value_str)
#             return "NOT (collection_ids && ARRAY[?])", params

#     elif op == FilterOperator.IN:
#         if not isinstance(value, list):
#             raise FilterError("$in for collection_id expects a list of values")
#         if not value:
#             # Empty list should produce FALSE
#             return "FALSE", params

#         # Check if all values are UUIDs
#         try:
#             valid_uuids = True
#             for v in value:
#                 if not isinstance(v, str) and not isinstance(v, uuid.UUID):
#                     valid_uuids = False
#                     break
#                 try:
#                     uuid.UUID(str(v))
#                 except (ValueError, TypeError):
#                     valid_uuids = False
#                     break

#             # Convert all values to strings
#             string_values = [str(v) for v in value]
#             params.append(string_values)

#             if valid_uuids:
#                 return "collection_ids && ?::uuid[]", params
#             else:
#                 return "collection_ids && ?::text[]", params
#         except Exception:
#             # Fallback to text array for any errors
#             params.append([str(v) for v in value])
#             return "collection_ids && ?::text[]", params

#     elif op == FilterOperator.NIN:
#         if not isinstance(value, list):
#             raise FilterError(
#                 "$nin for collection_id expects a list of values"
#             )
#         if not value:
#             # Empty list should produce TRUE (nothing to exclude)
#             return "TRUE", params

#         # Check if all values are UUIDs
#         try:
#             valid_uuids = True
#             for v in value:
#                 if not isinstance(v, str) and not isinstance(v, uuid.UUID):
#                     valid_uuids = False
#                     break
#                 try:
#                     uuid.UUID(str(v))
#                 except (ValueError, TypeError):
#                     valid_uuids = False
#                     break

#             # Convert all values to strings
#             string_values = [str(v) for v in value]
#             params.append(string_values)

#             if valid_uuids:
#                 return "NOT (collection_ids && ?::uuid[])", params
#             else:
#                 return "NOT (collection_ids && ?::text[])", params
#         except Exception:
#             # Fallback to text array for any errors
#             params.append([str(v) for v in value])
#             return "NOT (collection_ids && ?::text[])", params

#     elif op == FilterOperator.CONTAINS:
#         if isinstance(value, str) or isinstance(value, uuid.UUID):
#             value_str = str(value)
#             try:
#                 uuid.UUID(value_str)
#                 params.append(value_str)
#                 return "collection_ids @> ARRAY[?]::uuid", params
#             except (ValueError, TypeError):
#                 params.append(value_str)
#                 return "collection_ids @> ARRAY[?]", params
#         elif isinstance(value, list):
#             # Try to validate all values as UUIDs
#             try:
#                 valid_uuids = True
#                 string_values = []
#                 for v in value:
#                     v_str = str(v)
#                     try:
#                         uuid.UUID(v_str)
#                         string_values.append(v_str)
#                     except (ValueError, TypeError):
#                         valid_uuids = False
#                         string_values.append(v_str)

#                 params.append(string_values)

#                 if valid_uuids:
#                     return "collection_ids @> ?::uuid[]", params
#                 else:
#                     return "collection_ids @> ?::text[]", params
#             except Exception:
#                 # Fallback to text array
#                 params.append([str(v) for v in value])
#                 return "collection_ids @> ?::text[]", params
#         else:
#             raise FilterError(
#                 "$contains for collection_id expects a string or list of strings"
#             )

#     elif op == FilterOperator.OVERLAP:
#         values_to_use = []

#         if not isinstance(value, list):
#             if isinstance(value, str) or isinstance(value, uuid.UUID):
#                 values_to_use = [str(value)]
#             else:
#                 raise FilterError(
#                     "$overlap for collection_id expects a string or list of strings"
#                 )
#         else:
#             values_to_use = [str(v) for v in value]

#         # Try to validate all as UUIDs
#         try:
#             valid_uuids = True
#             for v_str in values_to_use:
#                 try:
#                     uuid.UUID(v_str)
#                 except (ValueError, TypeError):
#                     valid_uuids = False
#                     break

#             params.append(values_to_use)

#             if valid_uuids:
#                 return "collection_ids && ?::uuid[]", params
#             else:
#                 return "collection_ids && ?::text[]", params
#         except Exception:
#             # Fallback
#             params.append(values_to_use)
#             return "collection_ids && ?::text[]", params

#     else:
#         raise FilterError(f"Unsupported operator {op} for collection_id")


# def _build_collection_ids_condition(
#     op: str, value: Any, params: list[Any]
# ) -> tuple[str, list[Any]]:
#     """Build SQL condition for collection_ids field."""
#     if op == FilterOperator.EQ:
#         if not value:
#             # Empty value means no collections match (always false)
#             return "FALSE", params

#         # Array equality
#         if not isinstance(value, list):
#             value = [value]

#         collection_ids = [str(cid).strip() for cid in value if cid]
#         if not collection_ids:
#             return "FALSE", params

#         params.append(collection_ids)
#         return "collection_ids = ?", params

#     # Handle overlap operator
#     elif op == FilterOperator.OVERLAP:
#         if not value:
#             return "FALSE", params
        
#         if not isinstance(value, list):
#             value = [value]
        
#         collection_ids = [str(cid).strip() for cid in value if cid]
#         if not collection_ids:
#             return "FALSE", params
        
#         # Build explicit array construction with individual parameters
#         placeholders = []
#         for item in collection_ids:
#             params.append(item)
#             # Use positional parameter index instead of "?"
#             placeholders.append(f"${len(params)}")
        
#         return f"collection_ids && ARRAY[{', '.join(placeholders)}]::uuid[]", params

#     # Handle contains
#     elif op == FilterOperator.CONTAINS or op == FilterOperator.ARRAY_CONTAINS:
#         if not value:
#             return "FALSE", params

#         # For the test to pass, we need to handle array and scalar differently
#         if isinstance(value, list):
#             collection_ids = [str(cid).strip() for cid in value if cid]
#             if not collection_ids:
#                 return "FALSE", params

#             # Use jsonb for test compatibility
#             params.append(json.dumps(collection_ids))
#             return "collection_ids @> ?", params
#         else:
#             # Single value
#             params.append(json.dumps([str(value)]))
#             return "collection_ids @> ?", params

#     # Handle IN operator
#     elif op == FilterOperator.IN:
#         if not value or not isinstance(value, list):
#             return "FALSE", params

#         collection_ids = [str(cid).strip() for cid in value if cid]
#         if not collection_ids:
#             return "FALSE", params

#         # Use IN syntax with array overlap for array fields
#         params.append(collection_ids)
#         return "collection_ids && ?", params

#     # Handle NOT IN operator
#     elif op == FilterOperator.NIN:
#         if not value or not isinstance(value, list):
#             return "TRUE", params

#         collection_ids = [str(cid).strip() for cid in value if cid]
#         if not collection_ids:
#             return "TRUE", params

#         # Use NOT IN syntax with array overlap
#         params.append(collection_ids)
#         return "NOT (collection_ids && ?)", params

#     else:
#         raise FilterError(f"Unsupported operator for collection_ids: {op}")


# def _build_column_condition(
#     field: str, op: str, value: Any, params: list[Any]
# ) -> tuple[str, list[Any]]:
#     """Build SQL condition for a column."""
#     if op == FilterOperator.EQ:
#         if value is None:
#             return f"{field} IS NULL", params
#         else:
#             params.append(value)
#             return f"{field} = ?", params

#     elif op == FilterOperator.NE:
#         if value is None:
#             return f"{field} IS NOT NULL", params
#         else:
#             params.append(value)
#             return f"{field} != ?", params

#     elif op == FilterOperator.GT:
#         params.append(value)
#         return f"{field} > ?", params

#     elif op == FilterOperator.GTE:
#         params.append(value)
#         return f"{field} >= ?", params

#     elif op == FilterOperator.LT:
#         params.append(value)
#         return f"{field} < ?", params

#     elif op == FilterOperator.LTE:
#         params.append(value)
#         return f"{field} <= ?", params

#     elif op == FilterOperator.IN:
#         if not isinstance(value, list):
#             value = [value]

#         if not value:  # Empty list
#             return "FALSE", params

#         # Use proper IN syntax with placeholders
#         placeholders = []
#         for item in value:
#             params.append(item)
#             placeholders.append("?")
#         return f"{field} IN ({', '.join(placeholders)})", params

#     elif op == FilterOperator.NIN:
#         if not isinstance(value, list):
#             value = [value]

#         if not value:  # Empty list
#             return "TRUE", params

#         # Use proper NOT IN syntax with placeholders
#         placeholders = []
#         for item in value:
#             params.append(item)
#             placeholders.append("?")
#         return f"{field} NOT IN ({', '.join(placeholders)})", params

#     elif op == FilterOperator.LIKE:
#         # Add wildcards unless already present
#         if isinstance(value, str) and not (
#             value.startswith("%") or value.endswith("%")
#         ):
#             value = f"%{value}%"
#         params.append(value)
#         return f"{field} LIKE ?", params

#     elif op == FilterOperator.ILIKE:
#         # Add wildcards unless already present
#         if isinstance(value, str) and not (
#             value.startswith("%") or value.endswith("%")
#         ):
#             value = f"%{value}%"
#         params.append(value)
#         return f"{field} ILIKE ?", params

#     else:
#         raise FilterError(f"Unsupported operator for column: {op}")


# def _build_metadata_condition(
#     key: str, op: str, value: Any, params: list[Any], json_column: str
# ) -> tuple[str, list[Any]]:
#     """Build SQL condition for a metadata field."""
#     # Split the key into path components
#     path_parts = key.split(".")

#     # Build JSON path expression
#     if len(path_parts) == 1:
#         json_path_expr = f"{json_column}->'{key}'"
#     else:
#         # For nested keys, use #> operator with array of keys
#         json_path_expr = f"{json_column}#>'{{{','.join(path_parts)}}}'"

#     # Handle scalar operators
#     if op in FilterOperator.SCALAR_OPS:
#         # Map operators to SQL syntax
#         op_map = {
#             FilterOperator.EQ: "=",
#             FilterOperator.NE: "!=",
#             FilterOperator.LT: "<",
#             FilterOperator.LTE: "<=",
#             FilterOperator.GT: ">",
#             FilterOperator.GTE: ">=",
#             FilterOperator.LIKE: "LIKE",
#             FilterOperator.ILIKE: "ILIKE",
#         }

#         # Convert value to appropriate JSON format for comparison
#         if isinstance(value, bool):
#             params.append(value)
#             return f"{json_path_expr}::boolean {op_map[op]} ?", params
#         elif isinstance(value, (int, float)):
#             params.append(value)
#             return f"{json_path_expr}::numeric {op_map[op]} ?", params
#         else:
#             # String and other types
#             params.append(str(value))
#             return f"{json_path_expr}::text {op_map[op]} ?", params

#     # Handle array operators
#     elif op in FilterOperator.ARRAY_OPS:
#         # Ensure value is a JSON array
#         if not isinstance(value, list):
#             value = [value]

#         params.append(json.dumps(value))

#         # Map operators to PostgreSQL array operators
#         if op == FilterOperator.IN:
#             return (
#                 f"{json_path_expr}::text IN (SELECT jsonb_array_elements_text(?::jsonb))",
#                 params,
#             )
#         elif op == FilterOperator.NIN:
#             return (
#                 f"{json_path_expr}::text NOT IN (SELECT jsonb_array_elements_text(?::jsonb))",
#                 params,
#             )
#         else:
#             raise FilterError(
#                 f"Unsupported array operator for metadata field: {op}"
#             )

#     # Handle JSON operators
#     elif op in FilterOperator.JSON_OPS:
#         if op == FilterOperator.CONTAINS:
#             # For checking if object contains key/value pairs
#             params.append(json.dumps(value))
#             return f"{json_column}->'{key}' @> ?", params
#         elif op == FilterOperator.ARRAY_CONTAINS:
#             # For checking if array contains element
#             params.append(json.dumps(value))
#             return (
#                 f"(SELECT jsonb_path_exists({json_column}, '$.{key}[*] ? (@ == $v)', jsonb_build_object('v', ?::jsonb)))",
#                 params,
#             )
#         else:
#             raise FilterError(f"Unsupported JSON operator: {op}")

#     else:
#         raise FilterError(f"Unsupported operator for metadata field: {op}")


# def _build_json_path_expr(json_column: str, json_path: list[str]) -> str:
#     """Build a JSON path expression for a given column and path."""
#     path_expr = json_column
#     for p in json_path:
#         # Preserve special characters in the path component
#         path_expr += f"->'{p}'"
#     return path_expr


# def apply_filters(
#     filters: dict[str, Any],
#     top_level_columns=None,
#     mode: str = "where_clause",
#     json_column: str = "metadata",
#     params: Optional[list[Any]] = None,
# ) -> tuple[str, list[Any]]:
#     """
#     Applies a set of filters to generate SQL WHERE conditions.

#     Args:
#         filters: Dictionary of filters to apply
#         top_level_columns: Optional list of column names that are top-level in the table
#         mode: Output mode, either "where_clause" or "params_only"
#         json_column: Name of the JSON column in the table
#         params: List to append SQL parameters to

#     Returns:
#         Tuple of (SQL condition string, updated params list)
#     """
#     # Initialize parameters list if none provided
#     if params is None:
#         params = []

#     # Initialize top_level_columns with defaults if not provided
#     if top_level_columns is None or not top_level_columns:
#         top_level_columns = DEFAULT_TOP_LEVEL_COLUMNS
#     else:
#         # Convert list to set for faster lookups
#         top_level_columns = set(top_level_columns)
#         # Add explicitly passed columns to the default set
#         top_level_columns.update(DEFAULT_TOP_LEVEL_COLUMNS)

#     # Handle empty filter case
#     if not filters:
#         return "TRUE", params

#     # Process filter dictionary
#     condition, updated_params = _process_filter_dict(
#         filters, params, top_level_columns, json_column
#     )

#     if mode == "where_clause":
#         return condition, updated_params
#     elif mode == "params_only":
#         return "", updated_params
#     else:
#         raise FilterError(f"Unsupported filter mode: {mode}")
