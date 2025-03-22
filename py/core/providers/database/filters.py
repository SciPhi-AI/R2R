import json
from typing import Any

# Using lowercase list, dict, etc. to comply with pre-commit check
# and maintain backward compatibility
from py.core.providers.database.utils import psql_quote_literal

# List of column variables
COLUMN_VARS = [
    "id",
    "document_id",
    "owner_id",
    "collection_ids",
]


class FilterError(Exception):
    pass


class FilterOperator:
    EQ = "$eq"
    NE = "$ne"
    LT = "$lt"
    LTE = "$lte"
    GT = "$gt"
    GTE = "$gte"
    IN = "$in"
    NIN = "$nin"
    LIKE = "$like"
    ILIKE = "$ilike"
    CONTAINS = "$contains"
    AND = "$and"
    OR = "$or"
    OVERLAP = "$overlap"

    SCALAR_OPS = {EQ, NE, LT, LTE, GT, GTE, LIKE, ILIKE}
    ARRAY_OPS = {IN, NIN, OVERLAP}
    JSON_OPS = {CONTAINS}
    LOGICAL_OPS = {AND, OR}


def _process_logical_operator(
    op: str,
    conditions: list[dict],
    params: list[Any],
    top_level_columns: set[str],
    json_column: str,
) -> tuple[str, list[Any]]:
    """Process a logical operator ($and or $or) into SQL."""
    if not isinstance(conditions, list):
        raise FilterError(f"{op} value must be a list")

    parts = []
    for item in conditions:
        if not isinstance(item, dict):
            raise FilterError("Invalid filter format")

        sql, params = _process_filter_dict(
            item, params, top_level_columns, json_column
        )
        parts.append(f"({sql})")

    logical_connector = " AND " if op == FilterOperator.AND else " OR "
    return logical_connector.join(parts), params


def _process_field_condition(
    field: str,
    condition: dict[str, Any] | Any,
    params: list[Any],
    top_level_columns: set[str],
    json_column: str,
) -> tuple[str, list[Any]]:
    """Process a single field condition into SQL."""
    # Direct equality condition (shorthand)
    if not isinstance(condition, dict):
        return _build_operator_condition(
            field,
            FilterOperator.EQ,
            condition,
            params,
            top_level_columns,
            json_column,
        )

    # Operator-based condition
    if len(condition) != 1:
        raise FilterError(
            f"Condition for field {field} must have exactly one operator"
        )

    op, val = next(iter(condition.items()))

    # Validate operator
    allowed_ops = (
        FilterOperator.SCALAR_OPS
        | FilterOperator.ARRAY_OPS
        | FilterOperator.JSON_OPS
    )
    if op not in allowed_ops:
        raise FilterError(f"Unsupported operator: {op}")

    return _build_operator_condition(
        field, op, val, params, top_level_columns, json_column
    )


def _process_filter_dict(
    filters: dict[str, Any],
    params: list[Any],
    top_level_columns: set[str],
    json_column: str,
) -> tuple[str, list[Any]]:
    """Process a filter dictionary into SQL conditions."""
    # Check for logical operators first
    if len(filters) == 1:
        key = next(iter(filters.keys()))
        if key == FilterOperator.AND or key == FilterOperator.OR:
            return _process_logical_operator(
                key, filters[key], params, top_level_columns, json_column
            )

    # Process individual field conditions
    parts = []
    for field, condition in filters.items():
        sql, params = _process_field_condition(
            field, condition, params, top_level_columns, json_column
        )
        parts.append(sql)

    return " AND ".join(parts), params


def _build_operator_condition(
    field: str,
    op: str,
    value: Any,
    params: list[Any],
    top_level_columns: set[str],
    json_column: str,
) -> tuple[str, list[Any]]:
    """Build SQL for an operator condition with proper type handling."""
    # Special case for collection_id field
    if field == "collection_id":
        return _build_collection_id_condition(op, value, params)

    # Special case for parent_id
    if field == "parent_id":
        return _build_parent_id_condition(op, value, params)

    # Decide if it's a top-level column or metadata field
    field_is_metadata = field not in top_level_columns

    if field_is_metadata:
        return _build_metadata_condition(field, op, value, params, json_column)
    elif field == "collection_ids":
        return _build_collection_ids_condition(op, value, params)
    else:
        return _build_column_condition(field, op, value, params)


def _build_parent_id_condition(
    op: str, value: Any, params: list[Any]
) -> tuple[str, list[Any]]:
    """Build SQL condition for parent_id field (single UUID)."""
    param_idx = len(params) + 1

    if op == FilterOperator.EQ:
        if not isinstance(value, str):
            raise FilterError("$eq for parent_id expects a single UUID string")
        params.append(value)
        return f"parent_id = ${param_idx}::uuid", params

    elif op == FilterOperator.NE:
        if not isinstance(value, str):
            raise FilterError("$ne for parent_id expects a single UUID string")
        params.append(value)
        return f"parent_id != ${param_idx}::uuid", params

    elif op == FilterOperator.IN:
        if not isinstance(value, list):
            raise FilterError(
                "$in for parent_id expects a list of UUID strings"
            )
        params.append(value)
        return f"parent_id = ANY(${param_idx}::uuid[])", params

    elif op == FilterOperator.NIN:
        if not isinstance(value, list):
            raise FilterError(
                "$nin for parent_id expects a list of UUID strings"
            )
        params.append(value)
        return f"parent_id != ALL(${param_idx}::uuid[])", params

    else:
        raise FilterError(f"Unsupported operator {op} for parent_id")


def _build_collection_id_condition(
    op: str, value: Any, params: list[Any]
) -> tuple[str, list[Any]]:
    """Build SQL condition for collection_id field (shorthand for collection_ids array)."""
    param_idx = len(params) + 1

    if op == FilterOperator.EQ:
        if not isinstance(value, str):
            raise FilterError(
                "$eq for collection_id expects a single UUID string"
            )
        params.append([value])
        return f"collection_ids && ${param_idx}::uuid[]", params

    elif op == FilterOperator.NE:
        if not isinstance(value, str):
            raise FilterError(
                "$ne for collection_id expects a single UUID string"
            )
        params.append([value])
        return f"NOT (collection_ids && ${param_idx}::uuid[])", params

    elif op == FilterOperator.IN:
        if not isinstance(value, list):
            raise FilterError(
                "$in for collection_id expects a list of UUID strings"
            )
        params.append(value)
        return f"collection_ids && ${param_idx}::uuid[]", params

    elif op == FilterOperator.NIN:
        if not isinstance(value, list):
            raise FilterError(
                "$nin for collection_id expects a list of UUID strings"
            )
        params.append(value)
        return f"NOT (collection_ids && ${param_idx}::uuid[])", params

    elif op == FilterOperator.CONTAINS:
        if isinstance(value, str):
            params.append([value])
        elif isinstance(value, list):
            params.append(value)
        else:
            raise FilterError(
                "$contains for collection_id expects a UUID or list of UUIDs"
            )
        return f"collection_ids @> ${param_idx}::uuid[]", params

    elif op == FilterOperator.OVERLAP:
        if not isinstance(value, list):
            params.append([value])
        else:
            params.append(value)
        return f"collection_ids && ${param_idx}::uuid[]", params

    else:
        raise FilterError(f"Unsupported operator {op} for collection_id")


def _build_collection_ids_condition(
    op: str, value: Any, params: list[Any]
) -> tuple[str, list[Any]]:
    """Build SQL condition for collection_ids field (array of UUIDs)."""
    param_idx = len(params) + 1

    if op == FilterOperator.EQ:
        if not isinstance(value, list):
            raise FilterError(
                "$eq for collection_ids expects a list of UUID strings"
            )
        params.append(value)
        return f"collection_ids = ${param_idx}::uuid[]", params

    elif op == FilterOperator.CONTAINS:
        if isinstance(value, str):
            params.append([value])
        elif isinstance(value, list):
            params.append(value)
        else:
            raise FilterError(
                "$contains for collection_ids expects a UUID or list of UUIDs"
            )
        return f"collection_ids @> ${param_idx}::uuid[]", params

    elif op == FilterOperator.OVERLAP:
        if not isinstance(value, list):
            params.append([value])
        else:
            params.append(value)
        return f"collection_ids && ${param_idx}::uuid[]", params

    else:
        return _build_collection_id_condition(op, value, params)


def _build_column_condition(
    field: str, op: str, value: Any, params: list[Any]
) -> tuple[str, list[Any]]:
    """Build SQL condition for a standard column field."""
    param_idx = len(params) + 1

    if op == FilterOperator.EQ:
        params.append(value)
        return f"{field} = ${param_idx}", params

    elif op == FilterOperator.NE:
        params.append(value)
        return f"{field} != ${param_idx}", params

    elif op == FilterOperator.LT:
        params.append(value)
        return f"{field} < ${param_idx}", params

    elif op == FilterOperator.LTE:
        params.append(value)
        return f"{field} <= ${param_idx}", params

    elif op == FilterOperator.GT:
        params.append(value)
        return f"{field} > ${param_idx}", params

    elif op == FilterOperator.GTE:
        params.append(value)
        return f"{field} >= ${param_idx}", params

    elif op == FilterOperator.IN:
        if not isinstance(value, list):
            raise FilterError("argument to $in filter must be a list")
        params.append(value)
        return f"{field} = ANY(${param_idx})", params

    elif op == FilterOperator.NIN:
        if not isinstance(value, list):
            raise FilterError("argument to $nin filter must be a list")
        params.append(value)
        return f"{field} != ALL(${param_idx})", params

    elif op == FilterOperator.LIKE:
        params.append(value)
        return f"{field} LIKE ${param_idx}", params

    elif op == FilterOperator.ILIKE:
        params.append(value)
        return f"{field} ILIKE ${param_idx}", params

    else:
        raise FilterError(f"Unsupported operator {op} for column {field}")


def _build_metadata_condition(
    key: str, op: str, value: Any, params: list[Any], json_column: str
) -> tuple[str, list[Any]]:
    """Build SQL condition for a metadata field with proper JSON path handling."""
    param_idx = len(params) + 1

    # Strip "metadata." prefix if present
    key = key.removeprefix(f"{json_column}.")

    # Split on '.' to handle nested keys
    parts = key.split(".")

    # Determine if we need text extraction for scalar values
    use_text_extraction = op in (
        FilterOperator.LT,
        FilterOperator.LTE,
        FilterOperator.GT,
        FilterOperator.GTE,
        FilterOperator.EQ,
        FilterOperator.NE,
    ) and isinstance(value, (int, float, str))

    if (
        op == FilterOperator.IN
        or op == FilterOperator.CONTAINS
        or isinstance(value, (list, dict))
    ):
        use_text_extraction = False

    # Build the JSON path expression
    if len(parts) == 1:
        if use_text_extraction:
            path_expr = f"{json_column}->>'{parts[0]}'"
        else:
            path_expr = f"{json_column}->'{parts[0]}'"
    else:
        path_expr = json_column
        for p in parts[:-1]:
            path_expr += f"->'{p}'"
        last_part = parts[-1]
        if use_text_extraction:
            path_expr += f"->>'{last_part}'"
        else:
            path_expr += f"->'{last_part}'"

    # Convert numeric values to strings for text comparison
    def prepare_value(v):
        return str(v) if isinstance(v, (int, float)) else v

    if op == FilterOperator.EQ:
        if use_text_extraction:
            prepared_val = prepare_value(value)
            params.append(prepared_val)
            return f"{path_expr} = ${param_idx}", params
        else:
            params.append(json.dumps(value))
            return f"{path_expr} = ${param_idx}::jsonb", params

    elif op == FilterOperator.NE:
        if use_text_extraction:
            params.append(prepare_value(value))
            return f"{path_expr} != ${param_idx}", params
        else:
            params.append(json.dumps(value))
            return f"{path_expr} != ${param_idx}::jsonb", params

    elif op == FilterOperator.LT:
        params.append(prepare_value(value))
        return f"({path_expr})::numeric < ${param_idx}::numeric", params

    elif op == FilterOperator.LTE:
        params.append(prepare_value(value))
        return f"({path_expr})::numeric <= ${param_idx}::numeric", params

    elif op == FilterOperator.GT:
        params.append(prepare_value(value))
        return f"({path_expr})::numeric > ${param_idx}::numeric", params

    elif op == FilterOperator.GTE:
        params.append(prepare_value(value))
        return f"({path_expr})::numeric >= ${param_idx}::numeric", params

    elif op == FilterOperator.IN:
        if not isinstance(value, list):
            raise FilterError("argument to $in filter must be a list")

        if use_text_extraction:
            str_vals = [
                str(v) if isinstance(v, (int, float)) else v for v in value
            ]
            params.append(str_vals)
            return f"{path_expr} = ANY(${param_idx}::text[])", params

        # For JSON arrays, use containment checks with proper parameter indexing
        conditions = []
        for v in value:
            params.append(json.dumps(v))
            current_param_idx = len(params)
            conditions.append(f"{path_expr} @> ${current_param_idx}::jsonb")
        return f"({' OR '.join(conditions)})", params

    elif op == FilterOperator.CONTAINS:
        if isinstance(value, (str, int, float, bool)):
            value = [value]
        params.append(json.dumps(value))
        return f"{path_expr} @> ${param_idx}::jsonb", params

    else:
        raise FilterError(f"Unsupported operator {op} for metadata field")


def apply_filters(
    filters: dict[str, Any],
    params: list[Any],
    mode: str = "where_clause",
    top_level_columns: list[str] | None = None,
    json_column: str = "metadata",
) -> tuple[str, list[Any]]:
    """Apply filters with consistent WHERE clause handling.

    Args:
        filters: Dictionary of filter conditions
        params: Existing parameters list to extend
        mode: One of 'where_clause', 'condition_only', or 'append_only'
        top_level_columns: List of column names that aren't in metadata
        json_column: Name of the JSON column containing metadata

    Returns:
        Tuple of (SQL clause, updated parameters list)
    """
    if not filters:
        return "", params

    if top_level_columns is None:
        top_level_columns = COLUMN_VARS

    sql, updated_params = _process_filter_dict(
        filters, params, set(top_level_columns), json_column
    )

    if mode == "where_clause":
        return f"WHERE {sql}", updated_params
    elif mode == "condition_only":
        return sql, updated_params
    elif mode == "append_only":
        return f"AND {sql}", updated_params
    else:
        raise ValueError(f"Unknown filter mode: {mode}")
