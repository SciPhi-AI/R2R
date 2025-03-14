import json
from typing import Any, Optional, Tuple

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
        self.conditions: list[FilterCondition | "FilterExpression"] = []


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
        self.params: list[Any] = params  # mutated during construction
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
        """Simple quoting for demonstration.

        In production, use parameterized queries or your DB driver's quoting
        function instead.
        """
        return "'" + value.replace("'", "''") + "'"

    def _build_condition(self, cond: FilterCondition) -> str:
        field_is_metadata = cond.field not in self.top_level_columns
        key = cond.field
        op = cond.operator
        val = cond.value

        # 1. If the filter references "parent_id", handle it as a single-UUID column for graphs:
        if key == "parent_id":
            return self._build_parent_id_condition(op, val)

        # 2. If the filter references "collection_id", handle it as an array column (chunks)
        if key == "collection_id":
            return self._build_collection_id_condition(op, val)

        # 3. Otherwise, decide if it's top-level or metadata:
        if field_is_metadata:
            return self._build_metadata_condition(key, op, val)
        else:
            return self._build_column_condition(key, op, val)

    def _build_parent_id_condition(self, op: str, val: Any) -> str:
        """For 'graphs' tables, parent_id is a single UUID (not an array).

        We handle the same ops but in a simpler, single-UUID manner.
        """
        param_idx = len(self.params) + 1

        if op == "$eq":
            if not isinstance(val, str):
                raise FilterError(
                    "$eq for parent_id expects a single UUID string"
                )
            self.params.append(val)
            return f"parent_id = ${param_idx}::uuid"

        elif op == "$ne":
            if not isinstance(val, str):
                raise FilterError(
                    "$ne for parent_id expects a single UUID string"
                )
            self.params.append(val)
            return f"parent_id != ${param_idx}::uuid"

        elif op == "$in":
            # A list of UUIDs, any of which might match
            if not isinstance(val, list):
                raise FilterError(
                    "$in for parent_id expects a list of UUID strings"
                )
            self.params.append(val)
            return f"parent_id = ANY(${param_idx}::uuid[])"

        elif op == "$nin":
            # A list of UUIDs, none of which may match
            if not isinstance(val, list):
                raise FilterError(
                    "$nin for parent_id expects a list of UUID strings"
                )
            self.params.append(val)
            return f"parent_id != ALL(${param_idx}::uuid[])"

        else:
            # You could add more (like $gt, $lt, etc.) if your schema wants them
            raise FilterError(f"Unsupported operator {op} for parent_id")

    def _build_collection_id_condition(self, op: str, val: Any) -> str:
        """For the 'chunks' table, collection_ids is an array of UUIDs.

        This logic stays exactly as you had it.
        """
        param_idx = len(self.params) + 1

        if op == "$eq":
            if not isinstance(val, str):
                raise FilterError(
                    "$eq for collection_id expects a single UUID string"
                )
            self.params.append(val)
            return f"${param_idx}::uuid = ANY(collection_ids)"

        elif op == "$ne":
            if not isinstance(val, str):
                raise FilterError(
                    "$ne for collection_id expects a single UUID string"
                )
            self.params.append(val)
            return f"NOT (${param_idx}::uuid = ANY(collection_ids))"

        elif op == "$in":
            if not isinstance(val, list):
                raise FilterError(
                    "$in for collection_id expects a list of UUID strings"
                )
            self.params.append(val)
            return f"collection_ids && ${param_idx}::uuid[]"

        elif op == "$nin":
            if not isinstance(val, list):
                raise FilterError(
                    "$nin for collection_id expects a list of UUID strings"
                )
            self.params.append(val)
            return f"NOT (collection_ids && ${param_idx}::uuid[])"

        elif op == "$contains":
            if isinstance(val, str):
                # single string -> array with one element
                self.params.append([val])
                return f"collection_ids @> ${param_idx}::uuid[]"
            elif isinstance(val, list):
                self.params.append(val)
                return f"collection_ids @> ${param_idx}::uuid[]"
            else:
                raise FilterError(
                    "$contains for collection_id expects a UUID or list of UUIDs"
                )

        else:
            raise FilterError(f"Unsupported operator {op} for collection_id")

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
        key = key.removeprefix("metadata.")

        # Split on '.' to handle nested keys
        parts = key.split(".")

        # Use text extraction for scalar values, but not for arrays
        use_text_extraction = op in (
            "$lt",
            "$lte",
            "$gt",
            "$gte",
            "$eq",
            "$ne",
        ) and isinstance(val, (int, float, str))
        if op == "$in" or op == "$contains" or isinstance(val, (list, dict)):
            use_text_extraction = False

        # Build the JSON path expression
        if len(parts) == 1:
            if use_text_extraction:
                path_expr = f"{json_col}->>'{parts[0]}'"
            else:
                path_expr = f"{json_col}->'{parts[0]}'"
        else:
            path_expr = json_col
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

        if op == "$eq":
            if use_text_extraction:
                prepared_val = prepare_value(val)
                self.params.append(prepared_val)
                return f"{path_expr} = ${param_idx}"
            else:
                self.params.append(json.dumps(val))
                return f"{path_expr} = ${param_idx}::jsonb"
        elif op == "$ne":
            if use_text_extraction:
                self.params.append(prepare_value(val))
                return f"{path_expr} != ${param_idx}"
            else:
                self.params.append(json.dumps(val))
                return f"{path_expr} != ${param_idx}::jsonb"
        elif op == "$lt":
            self.params.append(prepare_value(val))
            return f"({path_expr})::numeric < ${param_idx}::numeric"
        elif op == "$lte":
            self.params.append(prepare_value(val))
            return f"({path_expr})::numeric <= ${param_idx}::numeric"
        elif op == "$gt":
            self.params.append(prepare_value(val))
            return f"({path_expr})::numeric > ${param_idx}::numeric"
        elif op == "$gte":
            self.params.append(prepare_value(val))
            return f"({path_expr})::numeric >= ${param_idx}::numeric"
        elif op == "$in":
            if not isinstance(val, list):
                raise FilterError("argument to $in filter must be a list")

            if use_text_extraction:
                str_vals = [
                    str(v) if isinstance(v, (int, float)) else v for v in val
                ]
                self.params.append(str_vals)
                return f"{path_expr} = ANY(${param_idx}::text[])"

            # For JSON arrays, use containment checks
            conditions = []
            for i, v in enumerate(val):
                self.params.append(json.dumps(v))
                conditions.append(f"{path_expr} @> ${param_idx + i}::jsonb")
            return f"({' OR '.join(conditions)})"

        elif op == "$contains":
            if isinstance(val, (str, int, float, bool)):
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
) -> tuple[str, list[Any]]:
    """Apply filters with consistent WHERE clause handling."""
    if not filters:
        return "", params

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
