import json
from typing import Any, Optional, Tuple, Union
from uuid import UUID

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


class FilterCondition:
    def __init__(self, field: str, operator: str, value: Any):
        self.field = field
        self.operator = operator
        self.value = value


class FilterExpression:
    def __init__(self, logical_op: Optional[str] = None):
        self.logical_op = logical_op
        self.conditions: list[Union[FilterCondition, "FilterExpression"]] = []


class FilterParser:
    def __init__(
        self,
        top_level_columns: Optional[list[str]] = None,
        json_column: str = "metadata",
    ):
        if top_level_columns is None:
            self.top_level_columns = set(COLUMN_VARS)
        else:
            self.top_level_columns = set(top_level_columns)
        self.json_column = json_column

    def parse(self, filters: dict) -> FilterExpression:
        if not filters:
            raise FilterError("Empty filters are not allowed")
        return self._parse_logical(filters)

    def _parse_logical(self, dct: dict) -> FilterExpression:
        keys = list(dct.keys())
        expr = FilterExpression()
        if len(keys) == 1 and keys[0] in (
            FilterOperator.AND,
            FilterOperator.OR,
        ):
            expr.logical_op = keys[0]
            if not isinstance(dct[keys[0]], list):
                raise FilterError(f"{keys[0]} value must be a list")
            for item in dct[keys[0]]:
                if isinstance(item, dict):
                    if self._is_logical_block(item):
                        expr.conditions.append(self._parse_logical(item))
                    else:
                        expr.conditions.append(
                            self._parse_condition_dict(item)
                        )
                else:
                    raise FilterError("Invalid filter format")
        else:
            expr.logical_op = FilterOperator.AND
            expr.conditions.append(self._parse_condition_dict(dct))

        return expr

    def _is_logical_block(self, dct: dict) -> bool:
        if len(dct.keys()) == 1:
            k = next(iter(dct.keys()))
            if k in FilterOperator.LOGICAL_OPS:
                return True
        return False

    def _parse_condition_dict(self, dct: dict) -> FilterExpression:
        expr = FilterExpression(logical_op=FilterOperator.AND)
        for field, cond in dct.items():
            if not isinstance(cond, dict):
                # direct equality
                expr.conditions.append(
                    FilterCondition(field, FilterOperator.EQ, cond)
                )
            else:
                if len(cond) != 1:
                    raise FilterError(
                        f"Condition for field {field} must have exactly one operator"
                    )
                op, val = next(iter(cond.items()))
                self._validate_operator(op)
                expr.conditions.append(FilterCondition(field, op, val))
        return expr

    def _validate_operator(self, op: str):
        allowed = (
            FilterOperator.SCALAR_OPS
            | FilterOperator.ARRAY_OPS
            | FilterOperator.JSON_OPS
            | FilterOperator.LOGICAL_OPS
        )
        if op not in allowed:
            raise FilterError(f"Unsupported operator: {op}")


class SQLFilterBuilder:
    def __init__(
        self,
        params: list[Any],
        top_level_columns: Optional[list[str]] = None,
        json_column: str = "metadata",
        mode: str = "where_clause",
    ):
        if top_level_columns is None:
            self.top_level_columns = set(COLUMN_VARS)
        else:
            self.top_level_columns = set(top_level_columns)
        self.json_column = json_column
        self.params: list[Any] = (
            params  # params are mutated during construction
        )
        self.mode = mode

    def build(self, expr: FilterExpression) -> Tuple[str, list[Any]]:
        where_clause = self._build_expression(expr)
        if self.mode == "where_clause":
            return f"WHERE {where_clause}", self.params

        return where_clause, self.params

    def _build_expression(self, expr: FilterExpression) -> str:
        parts = []
        for c in expr.conditions:
            if isinstance(c, FilterCondition):
                parts.append(self._build_condition(c))
            else:
                nested_sql = self._build_expression(c)
                parts.append(f"({nested_sql})")

        if expr.logical_op == FilterOperator.AND:
            return " AND ".join(parts)
        elif expr.logical_op == FilterOperator.OR:
            return " OR ".join(parts)
        else:
            return " AND ".join(parts)

    @staticmethod
    def _psql_quote_literal(value: str) -> str:
        """
        Safely quote a string literal for PostgreSQL to prevent SQL injection.
        This is a simple implementation - in production, you should use proper parameterization
        or your database driver's quoting functions.
        """
        return "'" + value.replace("'", "''") + "'"

    def _build_condition(self, cond: FilterCondition) -> str:
        field_is_metadata = cond.field not in self.top_level_columns
        key = cond.field
        op = cond.operator
        val = cond.value

        if field_is_metadata:
            return self._build_metadata_condition(key, op, val)
        else:
            return self._build_column_condition(key, op, val)

    def _build_column_condition(self, col: str, op: str, val: Any) -> str:
        param_idx = len(self.params) + 1
        if op == "$eq":
            self.params.append(val)
            return f"{col} = ${param_idx}"
        elif op == "$ne":
            self.params.append(val)
            return f"{col} != ${param_idx}"
        elif op == "$in":
            if not isinstance(val, list):
                raise FilterError("argument to $in filter must be a list")
            self.params.append(val)
            return f"{col} = ANY(${param_idx})"
        elif op == "$nin":
            if not isinstance(val, list):
                raise FilterError("argument to $nin filter must be a list")
            self.params.append(val)
            return f"{col} != ALL(${param_idx})"
        elif op == "$overlap":
            self.params.append(val)
            return f"{col} && ${param_idx}"
        elif op == "$contains":
            self.params.append(val)
            return f"{col} @> ${param_idx}"
        elif op == "$any":
            # If col == "collection_ids" handle special case
            if col == "collection_ids":
                self.params.append(f"%{val}%")
                return f"array_to_string({col}, ',') LIKE ${param_idx}"
            else:
                self.params.append(val)
                return f"${param_idx} = ANY({col})"
        elif op in ("$lt", "$lte", "$gt", "$gte"):
            self.params.append(val)
            return f"{col} {self._map_op(op)} ${param_idx}"
        else:
            raise FilterError(f"Unsupported operator for column {col}: {op}")

    def _build_metadata_condition(self, key: str, op: str, val: Any) -> str:
        param_idx = len(self.params) + 1
        json_col = self.json_column

        # Strip "metadata." prefix if present
        if key.startswith("metadata."):
            key = key[len("metadata.") :]

        # Split on '.' to handle nested keys
        parts = key.split(".")

        # Depending on the operator, decide whether we need text extraction (->>) for the last key
        # For JSON equality ($eq, $ne, $contains), we can stay JSON-based: use `->` for all segments.
        # For numeric comparisons ($lt, $gt, etc.), we need to extract text with `->>` at the last step to cast to float.
        # For $in (list checks), we probably need `->>` on the last segment to compare text.

        # Default: keep JSON structure all the way
        use_text_extraction = False
        if op in ("$lt", "$lte", "$gt", "$gte", "$in"):
            use_text_extraction = True

        # Build the JSON path expression
        # For all but the last part, use ->'part'
        # For the last part, use ->'part' or ->>'part' depending on use_text_extraction
        if len(parts) == 1:
            # Single part key
            if use_text_extraction:
                path_expr = f"{json_col}->>'{parts[0]}'"
            else:
                path_expr = f"{json_col}->'{parts[0]}'"
        else:
            # Multiple segments
            inner_parts = parts[:-1]
            last_part = parts[-1]
            # Build chain for the inner parts
            path_expr = json_col
            for p in inner_parts:
                path_expr += f"->'{p}'"
            # Last part
            if use_text_extraction:
                path_expr += f"->>'{last_part}'"
            else:
                path_expr += f"->'{last_part}'"

        # Now apply the operator logic as before, but use path_expr in place of {json_col}->'{key}'
        if op == "$eq":
            self.params.append(json.dumps(val))
            return f"{path_expr} = ${param_idx}::jsonb"
        elif op == "$ne":
            self.params.append(json.dumps(val))
            return f"{path_expr} != ${param_idx}::jsonb"
        elif op == "$lt":
            self.params.append(json.dumps(val))
            # path_expr already ends in ->>'last_part', so we can cast directly:
            return f"({path_expr})::float < (${param_idx}::jsonb)::float"
        elif op == "$lte":
            self.params.append(json.dumps(val))
            return f"({path_expr})::float <= (${param_idx}::jsonb)::float"
        elif op == "$gt":
            self.params.append(json.dumps(val))
            return f"({path_expr})::float > (${param_idx}::jsonb)::float"
        elif op == "$gte":
            self.params.append(json.dumps(val))
            return f"({path_expr})::float >= (${param_idx}::jsonb)::float"
        elif op == "$in":
            # For $in, we expect a list and compare as text
            if not isinstance(val, list):
                raise FilterError("argument to $in filter must be a list")
            self.params.append(val)
            # path_expr should end with ->>'last_part' for text extraction
            return f"({path_expr})::text = ANY(${param_idx}::text[])"
        elif op == "$contains":
            # $contains is JSON containment, no text extraction needed
            if isinstance(val, (int, float, str)):
                val = [val]
            self.params.append(json.dumps(val))
            return f"{path_expr} @> ${param_idx}::jsonb"
        else:
            raise FilterError(f"Unsupported operator for metadata field {op}")

    def _map_op(self, op: str) -> str:
        mapping = {
            FilterOperator.EQ: "=",
            FilterOperator.NE: "!=",
            FilterOperator.LT: "<",
            FilterOperator.LTE: "<=",
            FilterOperator.GT: ">",
            FilterOperator.GTE: ">=",
        }
        return mapping.get(op, op)


def apply_filters(
    filters: dict, params: list[Any], mode: str = "where_clause"
) -> str:
    """
    Apply filters with consistent WHERE clause handling
    """

    if not filters:
        return ""

    parser = FilterParser()
    expr = parser.parse(filters)
    builder = SQLFilterBuilder(params=params, mode=mode)
    filter_clause, new_params = builder.build(expr)

    if mode == "where_clause":
        return filter_clause, new_params  # Already includes WHERE
    elif mode == "condition_only":
        return filter_clause, new_params
    elif mode == "append_only":
        return f"AND {filter_clause}", new_params
    else:
        raise ValueError(f"Unknown filter mode: {mode}")
