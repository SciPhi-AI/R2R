import json
import uuid
from typing import Any, Optional, Set, Tuple


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
    ILIKE = "$ilike"  # Case-insensitive
    # Array Specific (for native PostgreSQL arrays like UUID[])
    OVERLAP = "$overlap"  # Check if arrays share any common elements (uses &&)
    ARRAY_CONTAINS = (
        "$contains"  # Check if array contains ALL specified elements (uses @>)
    )
    # JSONB Specific
    JSON_CONTAINS = "$json_contains"  # Check if JSONB contains the specified JSONB structure/value (uses @>)
    # Logical
    AND = "$and"
    OR = "$or"

    # Sets for easier checking
    SCALAR_OPS = {EQ, NE, LT, LTE, GT, GTE, LIKE, ILIKE}
    LIST_INPUT_OPS = {
        IN,
        NIN,
        OVERLAP,
        ARRAY_CONTAINS,
    }  # Ops requiring a list as input value
    LOGICAL_OPS = {AND, OR}
    # Note: JSON_CONTAINS can take various input types


# Default column names assumed to be top-level unless specified otherwise
DEFAULT_TOP_LEVEL_COLUMNS = {
    "id",
    "document_id",
    "owner_id",
    "collection_ids",  # Special handling as UUID[]
    "created_at",
    "updated_at",
    "status",
    "text",  # For potential direct filtering, though FTS is usually better
    "type",  # Example if you have a type column
    # Add other known top-level, non-JSONB columns here
}

# --- Error Class ---


class FilterError(ValueError):
    """Custom error for filter processing issues."""

    pass


# --- Helper for Parameter Management ---


class ParamHelper:
    """Manages SQL parameters and positional placeholder generation."""

    def __init__(self, initial_params: Optional[list[Any]] = None):
        self.params: list[Any] = initial_params or []
        self.index: int = len(self.params) + 1

    def add(self, value: Any) -> str:
        """Adds a parameter and returns its placeholder (e.g., '$1')."""
        self.params.append(value)
        placeholder = f"${self.index}"
        self.index += 1
        return placeholder


# --- Core Filter Processing Logic ---


def _process_filter_dict(
    filter_dict: dict[str, Any],
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
                raise FilterError(
                    f"'{FilterOperator.AND}' value must be a list of filter dictionaries."
                )
            if not value:
                # An empty $and is typically true (vacuously)
                conditions.append("TRUE")
                continue
            # FIX: Remove extra parentheses around recursive call result
            sub_conditions = [
                _process_filter_dict(
                    item, param_helper, top_level_columns, json_column
                )
                for item in value
                if isinstance(item, dict)
            ]
            # Filter out trivial TRUE conditions before joining
            sub_conditions = [sc for sc in sub_conditions if sc != "TRUE"]
            if sub_conditions:
                # Wrap individual sub-conditions in parens for clarity if joining multiple
                conditions.append(
                    " AND ".join(f"({sc})" for sc in sub_conditions)
                )

        elif key == FilterOperator.OR:
            if not isinstance(value, list):
                raise FilterError(
                    f"'{FilterOperator.OR}' value must be a list of filter dictionaries."
                )
            if not value:
                # An empty $or is typically false
                conditions.append("FALSE")
                continue
            # FIX: Remove extra parentheses around recursive call result
            sub_conditions = [
                _process_filter_dict(
                    item, param_helper, top_level_columns, json_column
                )
                for item in value
                if isinstance(item, dict)
            ]
            # Filter out trivial FALSE conditions before joining
            sub_conditions = [sc for sc in sub_conditions if sc != "FALSE"]
            if sub_conditions:
                # Wrap individual sub-conditions in parens for clarity if joining multiple
                conditions.append(
                    " OR ".join(f"({sc})" for sc in sub_conditions)
                )

        # Field Conditions
        else:
            field = key
            condition_spec = value
            sql_condition = _process_field_condition(
                field,
                condition_spec,
                param_helper,
                top_level_columns,
                json_column,
            )
            # Avoid adding trivial TRUE conditions directly
            if sql_condition != "TRUE":
                conditions.append(sql_condition)

    if not conditions:
        return "TRUE"

    # Join top-level conditions implicitly with AND, wrapping each in parentheses if needed
    # Filter out TRUE conditions before joining
    final_conditions = [c for c in conditions if c != "TRUE"]
    if not final_conditions:
        return "TRUE"
    # Wrap individual conditions only if there's more than one to join
    if len(final_conditions) > 1:
        return " AND ".join(f"({c})" for c in final_conditions)
    else:
        return final_conditions[
            0
        ]  # Return the single condition without extra parens


def _process_field_condition(
    field: str,
    condition_spec: Any,
    param_helper: ParamHelper,
    top_level_columns: Set[str],
    json_column: str,
) -> str:
    """Processes a condition for a specific field."""

    # Shorthand: 'collection_id' filter operates on 'collection_ids' array
    is_collection_id_shorthand = field == "collection_id"

    # Check if field specifically targets the 'collection_ids' array
    is_collection_ids_field = field == "collection_ids"

    # Check if the field is a top-level column *other* than the main json_column
    is_top_level_standard_col = (
        field in top_level_columns and field != json_column
    )

    # Determine if the field targets the json_column or its nested properties
    # Case 1: field name itself is the json_column name (e.g., "metadata") -> This implies nested structure inside condition_spec
    # Case 2: field name starts with json_column name + '.' (e.g., "metadata.key") -> Path within JSON
    # Case 3: field name is NOT a top-level column and NOT collection_id/collection_ids -> Assume it's a path within the default json_column
    relative_path = None
    is_metadata_target = False
    if field == json_column:
        is_metadata_target = True
        # We expect condition_spec to be a dict like {"path.to.key": value} or {"path": {op: val}}
        # This requires iterating condition_spec inside this block
    elif field.startswith(json_column + "."):
        is_metadata_target = True
        relative_path = field[
            len(json_column) + 1 :
        ]  # Get path part after "metadata."
    elif (
        not is_top_level_standard_col
        and not is_collection_id_shorthand
        and not is_collection_ids_field
    ):
        # Assume it's a path within the json_column by default if not recognized elsewhere
        is_metadata_target = True
        relative_path = field

    if is_collection_id_shorthand:
        # Treat collection_id as a filter on the collection_ids array
        # Usually implies checking for the presence of that single ID.
        # Map to $overlap for common use case.
        if isinstance(condition_spec, dict) and len(condition_spec) == 1:
            op, value = next(iter(condition_spec.items()))
            # Allow specific ops if needed, but default simple value to overlap
            if (
                op == FilterOperator.EQ
            ):  # Map $eq on shorthand to overlap check
                return _build_collection_ids_condition(
                    "collection_ids",
                    FilterOperator.OVERLAP,
                    [value],
                    param_helper,
                )
            elif (
                op == FilterOperator.NE
            ):  # Map $ne on shorthand to NOT overlap check (tricky, usually means "doesn't contain this one ID")
                # A strict != check is rare. More common is checking non-containment. Let's map to NOT &&
                return f"NOT (collection_ids && {_build_array_literal([value], param_helper, 'uuid')})"
            else:  # Allow other ops like $in, $nin directly if user specifies the operator
                return _build_collection_ids_condition(
                    "collection_ids", op, value, param_helper
                )
        elif isinstance(condition_spec, (str, uuid.UUID)):
            # Shorthand: collection_id: "some-uuid" means collection_ids overlaps with ["some-uuid"]
            return _build_collection_ids_condition(
                "collection_ids",
                FilterOperator.OVERLAP,
                [condition_spec],
                param_helper,
            )
        else:
            raise FilterError(
                f"Invalid condition for shorthand '{field}'. Expected UUID string or {{op: value}} dict."
            )

    elif is_collection_ids_field:
        # Direct operations on the collection_ids UUID[] field
        if isinstance(condition_spec, dict) and len(condition_spec) == 1:
            op, value = next(iter(condition_spec.items()))
            return _build_collection_ids_condition(
                field, op, value, param_helper
            )
        elif isinstance(condition_spec, list):
            # Shorthand: collection_ids: ["id1", "id2"] implies overlap
            return _build_collection_ids_condition(
                field, FilterOperator.OVERLAP, condition_spec, param_helper
            )
        else:
            raise FilterError(
                f"Invalid condition for '{field}'. Expected {{op: value}} dict or list of UUIDs."
            )

    elif is_metadata_target:
        if relative_path:
            # Field was like "metadata.key" - relative_path is "key"
            # Pass the relative path and the original condition_spec
            return _build_metadata_condition(
                relative_path, condition_spec, param_helper, json_column
            )
        else:
            # Field was just "metadata" - condition_spec must define paths/ops
            # Example: {"metadata": {"path.to.key": "value", "another.path": {"$gt": 5}}}
            if not isinstance(condition_spec, dict):
                raise FilterError(
                    f"Filter for '{json_column}' column must be a dictionary specifying paths and conditions."
                )

            # Process multiple conditions within the metadata structure, implicitly ANDing them
            metadata_conditions = []
            for meta_path, meta_condition_spec in condition_spec.items():
                # Recursively call _build_metadata_condition for each path
                condition_sql = _build_metadata_condition(
                    meta_path, meta_condition_spec, param_helper, json_column
                )
                if condition_sql != "TRUE":
                    metadata_conditions.append(condition_sql)

            if not metadata_conditions:
                return "TRUE"
            if len(metadata_conditions) == 1:
                return metadata_conditions[0]
            return " AND ".join(f"({mc})" for mc in metadata_conditions)

    elif is_top_level_standard_col:
        # Operations on standard, top-level SQL columns
        if isinstance(condition_spec, dict) and len(condition_spec) == 1:
            op, value = next(iter(condition_spec.items()))
            # Ensure the key is a valid operator
            if not op.startswith("$"):
                raise FilterError(
                    f"Invalid operator '{op}' for field '{field}'. Operators must start with '$'."
                )
            return _build_standard_column_condition(
                field, op, value, param_helper
            )
        else:
            # Shorthand: top_level_field: value means equality
            return _build_standard_column_condition(
                field, FilterOperator.EQ, condition_spec, param_helper
            )
    else:
        # Should not be reached if logic is correct
        raise FilterError(
            f"Could not determine filter type for field '{field}'."
        )


# --- Builder Functions for Specific Field Types ---


def _build_array_literal(
    items: list[Any], param_helper: ParamHelper, array_type: str
) -> str:
    """Helper to build ARRAY[...]::type[] literal with parameters."""
    if not items:
        return f"ARRAY[]::{array_type}[]"  # Handle empty array if needed elsewhere
    placeholders = [param_helper.add(item) for item in items]
    return f"ARRAY[{', '.join(placeholders)}]::{array_type}[]"


def _build_standard_column_condition(
    field: str, op: str, value: Any, param_helper: ParamHelper
) -> str:  # type: ignore
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
            return "FALSE"  # Or raise error? Let's return FALSE.

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
            raise FilterError(
                f"'{FilterOperator.LIKE}' requires a string value for field '{field}'."
            )
        placeholder = param_helper.add(
            value
        )  # Assume user includes wildcards if needed
        return f"{field} LIKE {placeholder}"
    elif op == FilterOperator.ILIKE:
        if not isinstance(value, str):
            raise FilterError(
                f"'{FilterOperator.ILIKE}' requires a string value for field '{field}'."
            )
        placeholder = param_helper.add(
            value
        )  # Assume user includes wildcards if needed
        return f"{field} ILIKE {placeholder}"

    # IN / NOT IN
    elif op == FilterOperator.IN:
        if not isinstance(value, list):
            raise FilterError(
                f"'{FilterOperator.IN}' requires a list value for field '{field}'."
            )
        if not value:
            return "FALSE"  # IN empty list is always false
        placeholders = [param_helper.add(item) for item in value]
        return f"{field} IN ({', '.join(placeholders)})"
    elif op == FilterOperator.NIN:
        if not isinstance(value, list):
            raise FilterError(
                f"'{FilterOperator.NIN}' requires a list value for field '{field}'."
            )
        if not value:
            return "TRUE"  # NOT IN empty list is always true
        placeholders = [param_helper.add(item) for item in value]
        return f"{field} NOT IN ({', '.join(placeholders)})"

    # If we get here, the operator is not supported
    raise FilterError(
        f"Unsupported operator '{op}' for standard column '{field}'."
    )


def _build_collection_ids_condition(
    target_column: str,  # Should always be 'collection_ids' when called
    op: str,
    value: Any,
    param_helper: ParamHelper,
) -> str:  # type: ignore
    """Builds SQL condition for the 'collection_ids' UUID[] array column."""
    if target_column != "collection_ids":
        raise FilterError(
            f"Internal Error: _build_collection_ids_condition called with target '{target_column}'"
        )

    # --- Operators requiring a list of UUIDs ---
    if op in [
        FilterOperator.OVERLAP,
        FilterOperator.ARRAY_CONTAINS,
        FilterOperator.IN,
        FilterOperator.NIN,
    ]:
        if not isinstance(value, list):
            raise FilterError(
                f"Operator '{op}' on '{target_column}' requires a list of UUID strings."
            )

        if not value:  # Empty list handling
            if op == FilterOperator.OVERLAP or op == FilterOperator.IN:
                return "FALSE"
            if op == FilterOperator.ARRAY_CONTAINS:
                return "TRUE"  # Contains all elements of an empty set is true
            if op == FilterOperator.NIN:
                return "TRUE"

        # Validate and convert values to UUID strings for the ARRAY constructor
        try:
            uuid_strings = [str(uuid.UUID(str(item))) for item in value]
        except (ValueError, TypeError) as e:
            raise FilterError(
                f"Invalid UUID format in list for '{target_column}' filter: {e}"
            ) from e

        array_literal = _build_array_literal(
            uuid_strings, param_helper, "uuid"
        )

        if (
            op == FilterOperator.OVERLAP or op == FilterOperator.IN
        ):  # IN on array means overlap
            return f"{target_column} && {array_literal}"
        elif (
            op == FilterOperator.ARRAY_CONTAINS
        ):  # Check if target_column contains ALL elements in value
            return f"{target_column} @> {array_literal}"
        elif (
            op == FilterOperator.NIN
        ):  # Check if target_column contains NONE of the elements in value
            return f"NOT ({target_column} && {array_literal})"

    # --- Operators requiring a single UUID (Less common for arrays, interpret carefully) ---
    elif (
        op == FilterOperator.EQ
    ):  # Check if array IS EXACTLY this single element array
        if isinstance(value, (str, uuid.UUID)):
            try:
                uuid_str = str(uuid.UUID(str(value)))
                placeholder = param_helper.add(uuid_str)
                return f"{target_column} = ARRAY[{placeholder}]::uuid[]"
            except (ValueError, TypeError) as e:
                raise FilterError(
                    f"Invalid UUID format for '{op}' on '{target_column}': {e}"
                ) from e
        else:
            raise FilterError(
                f"Operator '{op}' on '{target_column}' requires a single UUID string value."
            )

    elif (
        op == FilterOperator.NE
    ):  # Check if array IS NOT EXACTLY this single element array
        if isinstance(value, (str, uuid.UUID)):
            try:
                uuid_str = str(uuid.UUID(str(value)))
                placeholder = param_helper.add(uuid_str)
                return f"{target_column} != ARRAY[{placeholder}]::uuid[]"
            except (ValueError, TypeError) as e:
                raise FilterError(
                    f"Invalid UUID format for '{op}' on '{target_column}': {e}"
                ) from e
        else:
            raise FilterError(
                f"Operator '{op}' on '{target_column}' requires a single UUID string value."
            )

    raise FilterError(
        f"Unsupported operator '{op}' for array column '{target_column}'."
    )


def _build_metadata_condition(
    relative_path: str,
    condition_spec: Any,
    param_helper: ParamHelper,
    json_column: str,
) -> str:
    """
    Builds SQL condition for a potentially nested field within a JSONB column.

    Args:
        relative_path (str): The path to the field *within* the JSONB column (e.g., "key", "nested.key").
        condition_spec (Any): The condition to apply (e.g., "value", {"$gt": 5}, {"nested": "val"}).
        param_helper (ParamHelper): The parameter helper.
        json_column (str): The name of the JSONB column.

    Returns:
        str: The SQL condition string.
    """

    # Handle complex condition_spec (nested paths or operators)
    if isinstance(condition_spec, dict) and len(condition_spec) == 1:
        key, value = next(iter(condition_spec.items()))
        if key.startswith("$"):
            # It's an operator like {"$gt": 5} applied to relative_path
            op = key
            val = value
            return _build_metadata_operator_condition(
                relative_path, op, val, param_helper, json_column
            )
        else:
            # It's a nested path like {"inner": "value"} applied relative to relative_path
            # Combine paths and recursively call
            new_relative_path = f"{relative_path}.{key}"
            return _build_metadata_condition(
                new_relative_path, value, param_helper, json_column
            )
    else:
        # It's a direct value comparison (shorthand for EQ) like "value"
        # Apply EQ operator to the relative_path
        return _build_metadata_operator_condition(
            relative_path,
            FilterOperator.EQ,
            condition_spec,
            param_helper,
            json_column,
        )


def _build_metadata_operator_condition(
    relative_path: str,
    op: str,
    value: Any,
    param_helper: ParamHelper,
    json_column: str,
) -> str:
    """Builds the specific SQL for an operator on a JSONB path."""

    # Build JSON path expression based on relative_path
    path_parts = relative_path.split(".")
    use_text_extraction = op not in [
        FilterOperator.JSON_CONTAINS
    ]  # Use ->> or #>> for non-JSONB ops

    if len(path_parts) == 1:
        # Top-level key within the JSONB column
        json_accessor = (
            f"{json_column} ->> '{path_parts[0]}'"
            if use_text_extraction
            else f"{json_column} -> '{path_parts[0]}'"
        )
    else:
        # Nested path within the JSONB column
        # Ensure path parts are quoted if they contain special chars, though unlikely with '.' split
        # For simplicity, we assume standard identifiers here.
        path_literal = "{" + ",".join(path_parts) + "}"
        json_accessor = (
            f"{json_column} #>> '{path_literal}'"
            if use_text_extraction
            else f"{json_column} #> '{path_literal}'"
        )

    # Handle NULL comparisons against JSONB presence/value
    if value is None:
        # Determine the correct accessor to check for existence/JSON null
        # Use the non-text-extracting version for NULL checks
        null_check_accessor = (
            f"{json_column} -> '{path_parts[0]}'"
            if len(path_parts) == 1
            else f"{json_column} #> '{path_literal}'"
        )

        if op == FilterOperator.EQ:
            # Check if path exists AND value at path is JSON null
            return f"({null_check_accessor} IS NOT NULL AND {null_check_accessor} = 'null'::jsonb)"
        elif op == FilterOperator.NE:
            # Check if path does NOT exist OR if it exists and value is NOT JSON null
            return f"({null_check_accessor} IS NULL OR {null_check_accessor} != 'null'::jsonb)"
        else:
            # Other operators with SQL NULL usually result in NULL/FALSE in WHERE
            return "FALSE"

    # --- JSONB Contains ---
    if op == FilterOperator.JSON_CONTAINS:
        try:
            # Value needs to be valid JSON
            json_value_str = json.dumps(value)
            placeholder = param_helper.add(json_value_str)
            # Use the JSONB containment operator @>
            # Note: json_accessor uses '->' or '#>' here based on use_text_extraction logic above
            return f"{json_accessor} @> {placeholder}::jsonb"
        except TypeError as e:
            raise FilterError(
                f"Value for '{FilterOperator.JSON_CONTAINS}' on '{relative_path}' must be JSON serializable: {e}"
            ) from e

    # --- Standard comparisons (operating on text extraction ->> or #>>) ---
    # Ensure json_accessor uses text extraction here
    if (
        not use_text_extraction
    ):  # Should not happen based on logic above, but defensive check
        raise FilterError(
            f"Internal Error: Text extraction required for operator '{op}'"
        )

    sql_op_map = {
        FilterOperator.EQ: "=",
        FilterOperator.NE: "!=",
        FilterOperator.LT: "<",
        FilterOperator.LTE: "<=",
        FilterOperator.GT: ">",
        FilterOperator.GTE: ">=",
    }

    if op in sql_op_map:
        sql_operator = sql_op_map[op]
        # Determine appropriate casting based on value type for comparison
        if isinstance(value, bool):
            placeholder = param_helper.add(value)
            # Cast JSONB extracted text to boolean
            return f"({json_accessor})::boolean {sql_operator} {placeholder}"
        elif isinstance(value, (int, float)):
            placeholder = param_helper.add(value)
            # Cast JSONB extracted text to numeric for robust comparison
            return f"({json_accessor})::numeric {sql_operator} {placeholder}"
        elif isinstance(value, str):
            placeholder = param_helper.add(value)
            # Compare text directly
            return f"{json_accessor} {sql_operator} {placeholder}"
        else:
            # Fallback: Cast value to string and compare text representations
            placeholder = param_helper.add(str(value))
            return f"{json_accessor} {sql_operator} {placeholder}"

    # --- String Like ---
    elif op == FilterOperator.LIKE:
        if not isinstance(value, str):
            raise FilterError(
                f"'{FilterOperator.LIKE}' requires a string value for metadata field '{relative_path}'."
            )
        placeholder = param_helper.add(value)
        return f"{json_accessor} LIKE {placeholder}"
    elif op == FilterOperator.ILIKE:
        if not isinstance(value, str):
            raise FilterError(
                f"'{FilterOperator.ILIKE}' requires a string value for metadata field '{relative_path}'."
            )
        placeholder = param_helper.add(value)
        return f"{json_accessor} ILIKE {placeholder}"

    # --- IN / NOT IN (operating on text extraction) ---
    elif op == FilterOperator.IN:
        if not isinstance(value, list):
            raise FilterError(
                f"'{FilterOperator.IN}' requires a list value for metadata field '{relative_path}'."
            )
        if not value:
            return "FALSE"
        # Compare extracted text against a list of text values
        placeholders = [param_helper.add(str(item)) for item in value]
        # Wrap accessor in parentheses for IN operator
        return f"({json_accessor}) IN ({', '.join(placeholders)})"

    elif op == FilterOperator.NIN:
        if not isinstance(value, list):
            raise FilterError(
                f"'{FilterOperator.NIN}' requires a list value for metadata field '{relative_path}'."
            )
        if not value:
            return "TRUE"
        placeholders = [param_helper.add(str(item)) for item in value]
        # Wrap accessor in parentheses for NOT IN operator
        return f"({json_accessor}) NOT IN ({', '.join(placeholders)})"

    else:
        raise FilterError(
            f"Unsupported operator '{op}' for metadata field '{relative_path}'."
        )


# --- Public API Function ---


def apply_filters(
    filters: dict[str, Any],
    param_list: Optional[list[Any]] = None,  # Pass list to accumulate params
    top_level_columns: Optional[Set[str] | list[str]] = None,
    json_column: str = "metadata",
    mode: str = "where_clause",  # Controls output format
) -> Tuple[str, list[Any]]:
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
        raise TypeError("top_level_columns must be a Set, list, or None.")

    # Ensure json_column itself IS treated as a potential top-level key
    # but its processing is handled differently (expecting nested structure)
    # processed_top_level_columns.discard(json_column)

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
            raise FilterError(
                f"Unexpected error processing filters: {e}"
            ) from e

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
        raise FilterError(
            f"Unsupported filter mode: {mode}. Choose 'where_clause' or 'condition_only'."
        )
