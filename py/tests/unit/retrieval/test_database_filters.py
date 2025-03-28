import json
import pytest
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Add sys.path manipulation (if needed)
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the filter implementation components directly
from core.providers.database.filters import (
    FilterError,
    FilterOperator,
    ParamHelper,
    apply_filters,
    DEFAULT_TOP_LEVEL_COLUMNS,
    _process_filter_dict,
    _process_field_condition,
    _build_standard_column_condition,
    _build_collection_ids_condition,
    _build_metadata_condition,
    _build_metadata_operator_condition,
)

# Define test constants
UUID1 = str(uuid.uuid4())
UUID2 = str(uuid.uuid4())
UUID3 = str(uuid.uuid4())
JSON_COLUMN = "metadata"
TEST_TOP_LEVEL_COLS = DEFAULT_TOP_LEVEL_COLUMNS.copy()


# --- Unit Tests for Internal Helper Functions ---

class TestParamHelper:
    # Keep as is
    def test_initialization_empty(self):
        helper = ParamHelper()
        assert helper.params == []
        assert helper.index == 1
    def test_initialization_with_params(self):
        initial = ["param0"]
        helper = ParamHelper(initial)
        assert helper.params == initial
        assert helper.index == 2
    def test_add_param(self):
        helper = ParamHelper()
        ph1 = helper.add("value1")
        assert ph1 == "$1"
        assert helper.params == ["value1"]
        assert helper.index == 2
        ph2 = helper.add(123)
        assert ph2 == "$2"
        assert helper.params == ["value1", 123]
        assert helper.index == 3
    def test_add_multiple_params(self):
        initial = [True]
        helper = ParamHelper(initial)
        ph2 = helper.add("abc")
        ph3 = helper.add(None)
        assert ph2 == "$2"
        assert ph3 == "$3"
        assert helper.params == [True, "abc", None]
        assert helper.index == 4

class TestBuildStandardColumnCondition:
    # Keep as is
    @pytest.mark.parametrize("op, value, expected_sql, expected_params", [
        (FilterOperator.EQ, "val", "col = $1", ["val"]), (FilterOperator.EQ, 123, "col = $1", [123]),
        (FilterOperator.EQ, None, "col IS NULL", []), (FilterOperator.NE, "val", "col != $1", ["val"]),
        (FilterOperator.NE, None, "col IS NOT NULL", []), (FilterOperator.GT, 10, "col > $1", [10]),
        (FilterOperator.GTE, 10, "col >= $1", [10]), (FilterOperator.LT, 10, "col < $1", [10]),
        (FilterOperator.LTE, 10, "col <= $1", [10]), (FilterOperator.LIKE, "%pattern%", "col LIKE $1", ["%pattern%"]),
        (FilterOperator.ILIKE, "%pattern%", "col ILIKE $1", ["%pattern%"]),
        (FilterOperator.IN, ["a", "b"], "col IN ($1, $2)", ["a", "b"]), (FilterOperator.IN, [], "FALSE", []),
        (FilterOperator.NIN, ["a", "b"], "col NOT IN ($1, $2)", ["a", "b"]), (FilterOperator.NIN, [], "TRUE", []),
    ])
    def test_operators(self, op, value, expected_sql, expected_params):
        helper = ParamHelper(); sql = _build_standard_column_condition("col", op, value, helper)
        assert sql == expected_sql; assert helper.params == expected_params
    def test_unsupported_operator(self):
        helper = ParamHelper();
        with pytest.raises(FilterError, match="Unsupported operator"):
            _build_standard_column_condition("col", FilterOperator.OVERLAP, [], helper)
    def test_invalid_value_type_for_like(self):
        helper = ParamHelper();
        with pytest.raises(FilterError, match="requires a string value"):
            _build_standard_column_condition("col", FilterOperator.LIKE, 123, helper)
        with pytest.raises(FilterError, match="requires a string value"):
            _build_standard_column_condition("col", FilterOperator.ILIKE, 123, helper)
    def test_invalid_value_type_for_list_ops(self):
        helper = ParamHelper();
        with pytest.raises(FilterError, match="requires a list value"):
            _build_standard_column_condition("col", FilterOperator.IN, "not-a-list", helper)
        with pytest.raises(FilterError, match="requires a list value"):
            _build_standard_column_condition("col", FilterOperator.NIN, "not-a-list", helper)

class TestBuildCollectionIdsCondition:
    # Keep as is
    @pytest.mark.parametrize("op, value, expected_sql, expected_params", [
        (FilterOperator.OVERLAP, [UUID1], "collection_ids && ARRAY[$1]::uuid[]", [UUID1]),
        (FilterOperator.OVERLAP, [UUID1, UUID2], "collection_ids && ARRAY[$1,$2]::uuid[]", [UUID1, UUID2]),
        (FilterOperator.IN, [UUID1, UUID2], "collection_ids && ARRAY[$1,$2]::uuid[]", [UUID1, UUID2]),
        (FilterOperator.OVERLAP, [], "FALSE", []), (FilterOperator.IN, [], "FALSE", []),
        (FilterOperator.ARRAY_CONTAINS, [UUID1], "collection_ids @> ARRAY[$1]::uuid[]", [UUID1]),
        (FilterOperator.ARRAY_CONTAINS, [UUID1, UUID2], "collection_ids @> ARRAY[$1,$2]::uuid[]", [UUID1, UUID2]),
        (FilterOperator.ARRAY_CONTAINS, [], "TRUE", []),
        (FilterOperator.NIN, [UUID1], "NOT (collection_ids && ARRAY[$1]::uuid[])", [UUID1]),
        (FilterOperator.NIN, [UUID1, UUID2], "NOT (collection_ids && ARRAY[$1,$2]::uuid[])", [UUID1, UUID2]),
        (FilterOperator.NIN, [], "TRUE", []), (FilterOperator.EQ, UUID1, "collection_ids = ARRAY[$1]::uuid[]", [UUID1]),
        (FilterOperator.NE, UUID1, "collection_ids != ARRAY[$1]::uuid[]", [UUID1]),
    ])
    def test_operators(self, op, value, expected_sql, expected_params):
        helper = ParamHelper(); sql_direct = _build_collection_ids_condition("collection_ids", op, value, helper)
        assert sql_direct.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == expected_params
    def test_invalid_uuid(self):
        helper = ParamHelper();
        with pytest.raises(FilterError, match="Invalid UUID format"):
            _build_collection_ids_condition("collection_ids", FilterOperator.OVERLAP, ["invalid"], helper)
        with pytest.raises(FilterError, match="Invalid UUID format"):
            _build_collection_ids_condition("collection_ids", FilterOperator.ARRAY_CONTAINS, [UUID1, "invalid"], helper)
        with pytest.raises(FilterError, match="Invalid UUID format"):
            _build_collection_ids_condition("collection_ids", FilterOperator.EQ, "invalid", helper)
    def test_invalid_value_type_list(self):
        helper = ParamHelper();
        with pytest.raises(FilterError, match="requires a list"):
            _build_collection_ids_condition("collection_ids", FilterOperator.OVERLAP, UUID1, helper)
        with pytest.raises(FilterError, match="requires a list"):
            _build_collection_ids_condition("collection_ids", FilterOperator.ARRAY_CONTAINS, UUID1, helper)
    def test_invalid_value_type_single(self):
         helper = ParamHelper();
         with pytest.raises(FilterError, match="requires a single UUID"):
             _build_collection_ids_condition("collection_ids", FilterOperator.EQ, [UUID1], helper)
         with pytest.raises(FilterError, match="requires a single UUID"):
             _build_collection_ids_condition("collection_ids", FilterOperator.NE, [UUID1], helper)
    def test_unsupported_operator(self):
        helper = ParamHelper();
        with pytest.raises(FilterError, match="Unsupported operator"):
            _build_collection_ids_condition("collection_ids", FilterOperator.GT, [UUID1], helper)


# --- Corrected TestBuildMetadataCondition ---
class TestBuildMetadataCondition:
    json_col = JSON_COLUMN
    # Helper for safe compare SQL
    def _expected_safe_compare_sql(self, accessor, sql_op, param_placeholder, cast_type="numeric"):
        # Existing helper function - keep as is
        if cast_type == "numeric":
            return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        elif cast_type == "boolean":
             return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        else: # Includes string comparisons which don't need casting/null check here
            return f"{accessor} {sql_op} {param_placeholder}"

    # --- Test basic operators on simple path (Keep mostly as is, ensure consistency) ---
    @pytest.mark.parametrize("op, value, expected_sql_part, expected_params", [
        (FilterOperator.EQ, "val", f"->>'key' = $1", ["val"]),
        (FilterOperator.EQ, 123, None, [123]), # Numeric safe compare
        (FilterOperator.EQ, True, None, [True]), # Boolean safe compare
        (FilterOperator.NE, "val", f"->>'key' != $1", ["val"]),
        (FilterOperator.NE, 123, None, [123]), # Numeric safe compare
        (FilterOperator.NE, False, None, [False]), # Boolean safe compare
        (FilterOperator.GT, 10, None, [10]), # Numeric safe compare
        (FilterOperator.GTE, 10.5, None, [10.5]), # Numeric safe compare
        (FilterOperator.LT, 10, None, [10]), # Numeric safe compare
        (FilterOperator.LTE, 10.5, None, [10.5]), # Numeric safe compare
        (FilterOperator.GT, "abc", f"->>'key' > $1", ["abc"]), # String compare
        (FilterOperator.LIKE, "%pat%", f"->>'key' LIKE $1", ["%pat%"]),
        (FilterOperator.ILIKE, "%pat%", f"->>'key' ILIKE $1", ["%pat%"]),
        (FilterOperator.IN, ["a", "b"], f"->'key' ?| ARRAY[$1,$2]::text[]", ["a", "b"]), # JSONB array op
        (FilterOperator.IN, [], "FALSE", []),
        (FilterOperator.NIN, ["a", "b"], f"NOT ({JSON_COLUMN}->'key' ?| ARRAY[$1,$2]::text[])", ["a", "b"]), # JSONB array op
        (FilterOperator.NIN, [], "TRUE", []),
        (FilterOperator.JSON_CONTAINS, {"a": 1}, f"->'key' @> $1::jsonb", [json.dumps({"a": 1})]),
        (FilterOperator.JSON_CONTAINS, ["a", 1], f"->'key' @> $1::jsonb", [json.dumps(["a", 1])]),
        (FilterOperator.JSON_CONTAINS, "scalar", f"->'key' @> $1::jsonb", [json.dumps("scalar")]),
    ])
    def test_operators_simple_path(self, op, value, expected_sql_part, expected_params):
        helper = ParamHelper()
        condition_spec = {op: value}
        sql = _build_metadata_condition("key", condition_spec, helper, self.json_col)

        expected_sql_full = ""
        accessor = f"{self.json_col}->>'key'" # Base accessor for text

        # --- Logic to determine expected_sql_full (Keep as is from your corrected version) ---
        if isinstance(value, bool) and op in [FilterOperator.EQ, FilterOperator.NE]:
             sql_op_map = {FilterOperator.EQ:"=", FilterOperator.NE:"!="}
             expected_sql_full = self._expected_safe_compare_sql(accessor, sql_op_map[op], '$1', 'boolean')
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and op in [FilterOperator.EQ, FilterOperator.NE, FilterOperator.GT, FilterOperator.GTE, FilterOperator.LT, FilterOperator.LTE]:
             sql_op_map = {FilterOperator.EQ:"=", FilterOperator.NE:"!=", FilterOperator.GT:">", FilterOperator.GTE:">=", FilterOperator.LT:"<", FilterOperator.LTE:"<="}
             expected_sql_full = self._expected_safe_compare_sql(accessor, sql_op_map[op], '$1', 'numeric')
        elif value == [] and op == FilterOperator.IN: expected_sql_full = "FALSE"
        elif value == [] and op == FilterOperator.NIN: expected_sql_full = "TRUE"
        elif op == FilterOperator.JSON_CONTAINS:
             # Uses -> accessor, not ->>
             expected_sql_full = f"{self.json_col}{expected_sql_part}"
        elif op == FilterOperator.IN: # JSONB IN uses -> accessor
             expected_sql_full = f"{self.json_col}{expected_sql_part}"
        elif op == FilterOperator.NIN: # JSONB NIN uses -> accessor
             expected_sql_full = expected_sql_part # The NOT() part is already in expected_sql_part
        else: # Fallback (LIKE, ILIKE, GT>text, EQ/NE text) uses ->> accessor
             expected_sql_full = f"{self.json_col}{expected_sql_part}"

        assert sql.replace(" ", "") == expected_sql_full.replace(" ", "")
        assert helper.params == expected_params

    # --- Keep shorthand tests ---
    def test_eq_shorthand_simple_path(self):
        helper = ParamHelper(); condition_spec = "value"
        sql = _build_metadata_condition("key", condition_spec, helper, self.json_col)
        expected_sql = f"{self.json_col}->>'key' = $1"
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == ["value"]

    # --- UPDATED: Test operators on nested path (incorporating integration test patterns) ---
    @pytest.mark.parametrize("path, op, value, expected_sql_part, expected_params", [
        # Original nested examples (p1.p2)
        ("p1.p2", FilterOperator.EQ, "val", f"#>>'{{\"p1\",\"p2\"}}' = $1", ["val"]),
        ("p1.p2", FilterOperator.EQ, 123, None, [123]), # Numeric Safe Compare
        ("p1.p2", FilterOperator.LT, 0, None, [0]),     # Numeric Safe Compare
        ("p1.p2", FilterOperator.IN, ["x"], f"#>'{{\"p1\",\"p2\"}}' ?| ARRAY[$1]::text[]", ["x"]), # JSONB array op
        ("p1.p2", FilterOperator.JSON_CONTAINS, {"c": True}, f"#>'{{\"p1\",\"p2\"}}' @> $1::jsonb", [json.dumps({"c": True})]),

        # --- NEW: Cases inspired by integration test ---
        # metadata.category: {$eq: "ancient"} -> Nested path, string equality
        ("category", FilterOperator.EQ, "ancient", f"->>'category' = $1", ["ancient"]),
        # metadata.rating: {$lt: 5} -> Nested path, numeric comparison
        ("rating", FilterOperator.LT, 5, None, [5]), # Numeric Safe Compare
        # metadata.tags: {$contains: ["philosophy"]} -> Nested path, JSON_CONTAINS with list
        ("tags", FilterOperator.JSON_CONTAINS, ["philosophy"], f"->'tags' @> $1::jsonb", [json.dumps(["philosophy"])]),
        # Example with deeper nesting matching integration test style
        ("details.status", FilterOperator.NE, "pending", f"#>>'{{\"details\",\"status\"}}' != $1", ["pending"]),
        ("details.metrics.score", FilterOperator.GTE, 95.5, None, [95.5]), # Deeper Numeric Safe Compare
        ("details.flags", FilterOperator.JSON_CONTAINS, ["urgent", "review"], f"#>'{{\"details\",\"flags\"}}' @> $1::jsonb", [json.dumps(["urgent", "review"])]),
    ])
    def test_operators_nested_path(self, path, op, value, expected_sql_part, expected_params):
        helper = ParamHelper()
        condition_spec = {op: value}
        # This function should add the CORRECTLY encoded param to helper.params
        sql = _build_metadata_condition(path, condition_spec, helper, self.json_col)

        expected_sql_full = ""
        path_parts = path.split('.')
        if len(path_parts) == 1:
            text_accessor = f"{self.json_col}->>'{path_parts[0]}'"
            jsonb_accessor_prefix = f"{self.json_col}->"
            jsonb_accessor_suffix = f"'{path_parts[0]}'"
        else:
            quoted_path = '{' + ','.join(f'"{p}"' for p in path_parts) + '}'
            text_accessor = f"{self.json_col}#>>'{quoted_path}'"
            jsonb_accessor_prefix = f"{self.json_col}#>"
            jsonb_accessor_suffix = f"'{quoted_path}'"

        # --- Logic to determine expected_sql_full ---
        if isinstance(value, bool) and op in [FilterOperator.EQ, FilterOperator.NE]:
             sql_op_map = {FilterOperator.EQ:"=", FilterOperator.NE:"!="}
             expected_sql_full = self._expected_safe_compare_sql(text_accessor, sql_op_map[op], '$1', 'boolean')
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and op in [FilterOperator.EQ, FilterOperator.NE, FilterOperator.GT, FilterOperator.GTE, FilterOperator.LT, FilterOperator.LTE]:
             sql_op_map = {FilterOperator.EQ:"=", FilterOperator.NE:"!=", FilterOperator.GT:">", FilterOperator.GTE:">=", FilterOperator.LT:"<", FilterOperator.LTE:"<="}
             expected_sql_full = self._expected_safe_compare_sql(text_accessor, sql_op_map[op], '$1', 'numeric')
        elif value == [] and op == FilterOperator.IN: expected_sql_full = "FALSE"
        elif value == [] and op == FilterOperator.NIN: expected_sql_full = "TRUE"
        elif op == FilterOperator.JSON_CONTAINS:
             # Determine the correct SQL structure
             expected_sql_full = f"{jsonb_accessor_prefix}{jsonb_accessor_suffix} @> $1::jsonb"
             # !!! DO NOT MODIFY expected_params HERE !!!
             # expected_params = [json.dumps(p) for p in expected_params] # <<<--- THIS WAS THE ERROR - REMOVED
        elif op == FilterOperator.IN:
             placeholders = ','.join(f'${i+1}' for i in range(len(value)))
             expected_sql_full = f"{jsonb_accessor_prefix}{jsonb_accessor_suffix} ?| ARRAY[{placeholders}]::text[]"
        elif op == FilterOperator.NIN:
             placeholders = ','.join(f'${i+1}' for i in range(len(value)))
             expected_sql_full = f"NOT ({jsonb_accessor_prefix}{jsonb_accessor_suffix} ?| ARRAY[{placeholders}]::text[])"
        elif op in [FilterOperator.EQ, FilterOperator.NE, FilterOperator.GT, FilterOperator.GTE, FilterOperator.LT, FilterOperator.LTE, FilterOperator.LIKE, FilterOperator.ILIKE]:
             sql_op_map = {
                 FilterOperator.EQ: "=", FilterOperator.NE: "!=", FilterOperator.GT: ">", FilterOperator.GTE: ">=",
                 FilterOperator.LT: "<", FilterOperator.LTE: "<=", FilterOperator.LIKE: "LIKE", FilterOperator.ILIKE: "ILIKE"
             }
             expected_sql_full = f"{text_accessor} {sql_op_map[op]} $1"
        else:
            pytest.fail(f"Unhandled operator {op} in nested path test logic")

        # This comparison checks the generated SQL structure
        assert sql.replace(" ", "") == expected_sql_full.replace(" ", "")

        # This comparison checks the generated parameters against the expectation from parametrize
        # The expectation from parametrize should ALREADY be correctly formatted (e.g., json.dumps applied there)
        assert helper.params == expected_params



    # --- Keep other nested path tests (shorthand, structure) ---
    def test_eq_shorthand_nested_path(self):
        helper = ParamHelper(); condition_spec = "value"
        sql = _build_metadata_condition("p1.p2", condition_spec, helper, self.json_col)
        expected_sql = f"{self.json_col}#>>'{{\"p1\",\"p2\"}}' = $1"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == ["value"]

    # Test case where the *value* defines the nested structure
    def test_nested_structure_condition(self):
        helper = ParamHelper(); condition_spec = {"p2": "value"}
        sql = _build_metadata_condition("p1", condition_spec, helper, self.json_col)
        # This correctly resolves to filtering on p1.p2
        expected_sql = f"{self.json_col}#>>'{{\"p1\",\"p2\"}}' = $1"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == ["value"]

    def test_nested_structure_condition_with_op(self):
        helper = ParamHelper(); condition_spec = {"p2": {FilterOperator.GT: 5}}
        sql = _build_metadata_condition("p1", condition_spec, helper, self.json_col)
        # Correctly resolves to filtering on p1.p2 with GT
        accessor = f"{self.json_col}#>>'{{\"p1\",\"p2\"}}'"
        expected_sql = self._expected_safe_compare_sql(accessor, '>', '$1', 'numeric')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == [5]


    # --- Keep Null Handling Tests ---
    def test_null_handling_simple(self):
        helper_eq = ParamHelper(); sql_eq = _build_metadata_condition("key", {FilterOperator.EQ: None}, helper_eq, self.json_col)
        expected_sql_eq = f"{self.json_col}->>'key' IS NULL"; assert sql_eq.replace(" ", "") == expected_sql_eq.replace(" ",""); assert helper_eq.params == []
        helper_ne = ParamHelper(); sql_ne = _build_metadata_condition("key", {FilterOperator.NE: None}, helper_ne, self.json_col)
        expected_sql_ne = f"{self.json_col}->>'key' IS NOT NULL"; assert sql_ne.replace(" ", "") == expected_sql_ne.replace(" ",""); assert helper_ne.params == []

    def test_null_handling_nested(self):
        helper_eq = ParamHelper(); sql_eq = _build_metadata_condition("p1.p2", {FilterOperator.EQ: None}, helper_eq, self.json_col)
        expected_sql_eq = f"{self.json_col}#>>'{{\"p1\",\"p2\"}}' IS NULL"; assert sql_eq.replace(" ", "") == expected_sql_eq.replace(" ",""); assert helper_eq.params == []
        helper_ne = ParamHelper(); sql_ne = _build_metadata_condition("p1.p2", {FilterOperator.NE: None}, helper_ne, self.json_col)
        expected_sql_ne = f"{self.json_col}#>>'{{\"p1\",\"p2\"}}' IS NOT NULL"; assert sql_ne.replace(" ", "") == expected_sql_ne.replace(" ",""); assert helper_ne.params == []

    # --- Keep JSONB Array Operator tests (already handle simple/nested) ---
    @pytest.mark.parametrize("op, value, expected_sql_part, expected_params", [
        (FilterOperator.IN, ["a", "b"], f"->'tags' ?| ARRAY[$1,$2]::text[]", ["a", "b"]),
        (FilterOperator.IN, ["single"], f"->'tags' ?| ARRAY[$1]::text[]", ["single"]),
        (FilterOperator.IN, [], "FALSE", []),
        (FilterOperator.NIN, ["a", "b"], f"NOT ({JSON_COLUMN}->'tags' ?| ARRAY[$1,$2]::text[])", ["a", "b"]),
        (FilterOperator.NIN, ["single"], f"NOT ({JSON_COLUMN}->'tags' ?| ARRAY[$1]::text[])", ["single"]),
        (FilterOperator.NIN, [], "TRUE", []),
    ])
    def test_jsonb_array_operators_simple_path(self, op, value, expected_sql_part, expected_params):
        helper = ParamHelper(); condition_spec = {op: value}
        sql = _build_metadata_condition("tags", condition_spec, helper, self.json_col)
        expected_sql_full = ""
        if op == FilterOperator.IN and not value: expected_sql_full = "FALSE"
        elif op == FilterOperator.NIN and not value: expected_sql_full = "TRUE"
        elif op == FilterOperator.NIN: expected_sql_full = expected_sql_part # NOT is part of expected_sql_part
        else: expected_sql_full = f"{self.json_col}{expected_sql_part}" # Uses -> accessor
        assert sql.replace(" ", "") == expected_sql_full.replace(" ", ""); assert helper.params == expected_params

    @pytest.mark.parametrize("op, value, expected_sql_part, expected_params", [
        (FilterOperator.IN, ["legacy"], f"#>'{{\"version\",\"tags\"}}' ?| ARRAY[$1]::text[]", ["legacy"]),
        (FilterOperator.IN, ["stable", "beta"], f"#>'{{\"version\",\"tags\"}}' ?| ARRAY[$1,$2]::text[]", ["stable", "beta"]),
        (FilterOperator.IN, [], "FALSE", []),
        (FilterOperator.NIN, ["legacy"], f"NOT ({JSON_COLUMN}#>'{{\"version\",\"tags\"}}' ?| ARRAY[$1]::text[])", ["legacy"]),
        (FilterOperator.NIN, ["stable", "beta"], f"NOT ({JSON_COLUMN}#>'{{\"version\",\"tags\"}}' ?| ARRAY[$1,$2]::text[])", ["stable", "beta"]),
        (FilterOperator.NIN, [], "TRUE", []),
    ])
    def test_jsonb_array_operators_nested_path(self, op, value, expected_sql_part, expected_params):
        helper = ParamHelper(); condition_spec = {op: value}
        sql = _build_metadata_condition("version.tags", condition_spec, helper, self.json_col)
        expected_sql_full = ""
        if op == FilterOperator.IN and not value: expected_sql_full = "FALSE"
        elif op == FilterOperator.NIN and not value: expected_sql_full = "TRUE"
        elif op == FilterOperator.NIN: expected_sql_full = expected_sql_part # NOT is part of expected_sql_part
        else: expected_sql_full = f"{self.json_col}{expected_sql_part}" # Uses #> accessor
        assert sql.replace(" ", "") == expected_sql_full.replace(" ", ""); assert helper.params == expected_params


    # --- Keep Error Handling Tests ---
    def test_unsupported_operator(self):
        helper = ParamHelper(); condition_spec = {FilterOperator.OVERLAP: []} # OVERLAP not supported for general metadata
        with pytest.raises(FilterError, match="Unsupported operator"):
            _build_metadata_condition("key", condition_spec, helper, self.json_col)

    def test_json_contains_non_serializable(self):
        helper = ParamHelper(); condition_spec = {FilterOperator.JSON_CONTAINS: {"a": {1, 2}}} # Set is not JSON serializable
        with pytest.raises(FilterError, match="must be JSON serializable"):
             _build_metadata_condition("key", condition_spec, helper, self.json_col)

    # NEW: Test specifically for $contains mapping to JSON_CONTAINS
    def test_contains_operator_maps_to_json_contains_simple(self):
        helper = ParamHelper()
        # Simulate the filter structure from the integration test
        # Note: The FilterOperator enum likely doesn't have 'CONTAINS', use JSON_CONTAINS
        condition_spec = {FilterOperator.JSON_CONTAINS: ["philosophy"]}
        sql = _build_metadata_condition("tags", condition_spec, helper, self.json_col)
        expected_sql = f"{self.json_col}->'tags' @> $1::jsonb"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == [json.dumps(["philosophy"])]

    def test_contains_operator_maps_to_json_contains_nested(self):
        helper = ParamHelper()
        condition_spec = {FilterOperator.JSON_CONTAINS: ["urgent"]}
        sql = _build_metadata_condition("details.flags", condition_spec, helper, self.json_col)
        expected_sql = f"{self.json_col}#>'{{\"details\",\"flags\"}}' @> $1::jsonb"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == [json.dumps(["urgent"])]


# --- Corrected TestProcessFieldCondition (Keep as is from previous correction) ---
class TestProcessFieldCondition:
    top_cols = TEST_TOP_LEVEL_COLS; json_col = JSON_COLUMN
    def _expected_safe_compare_sql(self, accessor, sql_op, param_placeholder, cast_type="numeric"):
        if cast_type == "numeric": return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        elif cast_type == "boolean": return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        else: return f"{accessor} {sql_op} {param_placeholder}"
    def test_routes_collection_id_shorthand_single_value(self):
        helper = ParamHelper(); sql = _process_field_condition("collection_id", UUID1, helper, self.top_cols, self.json_col)
        assert "collection_ids&&ARRAY[$1]::uuid[]" == sql.replace(" ",""); assert helper.params == [UUID1]
    def test_routes_collection_id_shorthand_eq_op(self):
        helper = ParamHelper(); sql = _process_field_condition("collection_id", {FilterOperator.EQ: UUID1}, helper, self.top_cols, self.json_col)
        assert "collection_ids&&ARRAY[$1]::uuid[]" == sql.replace(" ",""); assert helper.params == [UUID1]
    def test_routes_collection_id_shorthand_ne_op(self):
        helper = ParamHelper(); sql = _process_field_condition("collection_id", {FilterOperator.NE: UUID1}, helper, self.top_cols, self.json_col)
        assert "NOT(collection_ids&&ARRAY[$1]::uuid[])" == sql.replace(" ",""); assert helper.params == [UUID1]
    def test_routes_collection_id_shorthand_in_op(self):
        helper = ParamHelper(); sql = _process_field_condition("collection_id", {FilterOperator.IN: [UUID1, UUID2]}, helper, self.top_cols, self.json_col)
        assert "collection_ids&&ARRAY[$1,$2]::uuid[]" == sql.replace(" ",""); assert helper.params == [UUID1, UUID2]
    def test_routes_collection_ids_direct_op(self):
        helper = ParamHelper(); sql = _process_field_condition("collection_ids", {FilterOperator.OVERLAP: [UUID1, UUID2]}, helper, self.top_cols, self.json_col)
        assert "collection_ids&&ARRAY[$1,$2]::uuid[]" == sql.replace(" ",""); assert helper.params == [UUID1, UUID2]
    def test_routes_collection_ids_shorthand_list(self):
         helper = ParamHelper(); sql = _process_field_condition("collection_ids", [UUID1, UUID2], helper, self.top_cols, self.json_col)
         assert "collection_ids&&ARRAY[$1,$2]::uuid[]" == sql.replace(" ",""); assert helper.params == [UUID1, UUID2]
    def test_routes_standard_column_shorthand_eq(self):
        helper = ParamHelper(); sql = _process_field_condition("owner_id", UUID1, helper, self.top_cols, self.json_col)
        assert "owner_id=$1" == sql.replace(" ", ""); assert helper.params == [UUID1]
    def test_routes_standard_column_op(self):
        helper = ParamHelper(); sql = _process_field_condition("status", {FilterOperator.NE: "active"}, helper, self.top_cols, self.json_col)
        assert "status!=$1" == sql.replace(" ", ""); assert helper.params == ["active"]
    def test_routes_metadata_shorthand_eq_implicit(self):
        helper = ParamHelper(); sql = _process_field_condition("tags", "urgent", helper, self.top_cols, json_column=self.json_col)
        expected_sql = f"{self.json_col}->>'tags'=$1"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == ["urgent"]
    def test_routes_metadata_op_implicit(self):
        helper = ParamHelper(); sql = _process_field_condition("score", {FilterOperator.GT: 90}, helper, self.top_cols, self.json_col)
        accessor = f"{self.json_col}->>'score'"; expected_sql = self._expected_safe_compare_sql(accessor, '>', '$1', 'numeric')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == [90]
    def test_routes_metadata_nested_shorthand_eq_implicit(self):
        helper = ParamHelper(); sql = _process_field_condition("nested.value", True, helper, self.top_cols, self.json_col)
        accessor = f"{self.json_col}#>>'{{\"nested\",\"value\"}}'"; expected_sql = self._expected_safe_compare_sql(accessor, '=', '$1', 'boolean')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == [True]
    def test_routes_metadata_nested_structure_implicit(self):
        helper = ParamHelper(); sql = _process_field_condition("nested", {"value": True}, helper, self.top_cols, self.json_col)
        accessor = f"{self.json_col}#>>'{{\"nested\",\"value\"}}'"; expected_sql = self._expected_safe_compare_sql(accessor, '=', '$1', 'boolean')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == [True]
    def test_routes_metadata_nested_structure_op_implicit(self):
        helper = ParamHelper(); sql = _process_field_condition("nested", {"value": {FilterOperator.GT: 5}}, helper, self.top_cols, self.json_col)
        accessor = f"{self.json_col}#>>'{{\"nested\",\"value\"}}'"; expected_sql = self._expected_safe_compare_sql(accessor, '>', '$1', 'numeric')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == [5]
    def test_routes_metadata_explicit_path_shorthand(self):
        helper = ParamHelper(); sql = _process_field_condition(f"{self.json_col}.key", "value", helper, self.top_cols, json_column=self.json_col)
        expected_sql = f"{self.json_col}->>'key'=$1"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == ["value"]
    def test_routes_metadata_explicit_path_op(self):
        helper = ParamHelper(); sql = _process_field_condition(f"{self.json_col}.score", {FilterOperator.LTE: 100}, helper, self.top_cols, json_column=self.json_col)
        accessor = f"{self.json_col}->>'score'"; expected_sql = self._expected_safe_compare_sql(accessor, '<=', '$1', 'numeric')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == [100]
    def test_routes_metadata_explicit_column_nested_structure(self):
        helper = ParamHelper(); condition_spec = {"path.to.key": "val", "another": {FilterOperator.NE: False}}
        sql = _process_field_condition(self.json_col, condition_spec, helper, self.top_cols, json_column=self.json_col)
        expected_part1 = f"{self.json_col}#>>'{{\"path\",\"to\",\"key\"}}'=$1"; accessor2 = f"{self.json_col}->>'another'"
        expected_part2 = self._expected_safe_compare_sql(accessor2, '!=', '$2', 'boolean')
        expected_sql = f"({expected_part1})AND({expected_part2})"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert helper.params == ["val", False]

# --- Corrected TestProcessFilterDict (Keep as is from previous correction) ---
class TestProcessFilterDict:
    top_cols = TEST_TOP_LEVEL_COLS; json_col = JSON_COLUMN
    def _expected_safe_compare_sql(self, accessor, sql_op, param_placeholder, cast_type="numeric"):
        if cast_type == "numeric": return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        elif cast_type == "boolean": return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        else: return f"{accessor} {sql_op} {param_placeholder}"
    def test_empty_dict(self):
        helper = ParamHelper(); sql = _process_filter_dict({}, helper, self.top_cols, self.json_col)
        assert sql == "TRUE"; assert helper.params == []
    def test_single_field_condition(self):
        helper = ParamHelper(); filters = {"id": UUID1}; sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "id = $1"; assert helper.params == [UUID1]
    def test_multiple_field_conditions_implicit_and(self):
        helper = ParamHelper(); filters = {"id": UUID1, "status": "active"}; sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        expected_sql1 = "(id = $1) AND (status = $2)"; expected_sql2 = "(status = $1) AND (id = $2)"; actual_sql = sql.replace(" ","")
        assert actual_sql == expected_sql1.replace(" ","") or actual_sql == expected_sql2.replace(" ",""); assert set(helper.params) == {UUID1, "active"}
    def test_logical_and(self):
        helper = ParamHelper(); filters = {FilterOperator.AND: [{"id": UUID1}, {"status": "active"}]}; sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "(id = $1) AND (status = $2)"; assert helper.params == [UUID1, "active"]
    def test_logical_or(self):
        helper = ParamHelper(); filters = {FilterOperator.OR: [{"id": UUID1}, {"status": "active"}]}; sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "(id = $1) OR (status = $2)"; assert helper.params == [UUID1, "active"]
    def test_nested_logical(self):
        helper = ParamHelper(); filters = { FilterOperator.AND: [ {"id": UUID1}, {FilterOperator.OR: [{"status": "active"}, {"score": {FilterOperator.GT: 90}}]} ] }
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col); accessor = f"{self.json_col}->>'score'"
        score_condition = self._expected_safe_compare_sql(accessor, '>', '$3', 'numeric'); expected_sql = f"(id = $1) AND ((status = $2) OR ({score_condition}))"
        assert sql.replace(" ","") == expected_sql.replace(" ",""); assert helper.params == [UUID1, "active", 90]
    def test_empty_logical_and(self):
        helper = ParamHelper(); filters = {FilterOperator.AND: []}; sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "TRUE"; assert helper.params == []
    def test_empty_logical_or(self):
        helper = ParamHelper(); filters = {FilterOperator.OR: []}; sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "FALSE"; assert helper.params == []

# --- Corrected TestApplyFiltersApi (Keep as is from previous correction) ---
class TestApplyFiltersApi:
    json_column = JSON_COLUMN
    def _expected_safe_compare_sql(self, accessor, sql_op, param_placeholder, cast_type="numeric"):
        if cast_type == "numeric": return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        elif cast_type == "boolean": return f"({accessor} IS NOT NULL AND ({accessor})::{cast_type} {sql_op} {param_placeholder})"
        else: return f"{accessor} {sql_op} {param_placeholder}"
    def test_simple_equality_filter(self):
        filters = {"id": UUID1}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "id = $1"; assert params == [UUID1]
    def test_operator_equality_filter(self):
        filters = {"id": {FilterOperator.EQ: UUID1}}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "id = $1"; assert params == [UUID1]
    def test_and_operator(self):
        filters = {FilterOperator.AND: [{"id": UUID1}, {"owner_id": UUID2}]}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "(id = $1) AND (owner_id = $2)"; assert params == [UUID1, UUID2]
    def test_or_operator(self):
        filters = {FilterOperator.OR: [{"id": UUID1}, {"owner_id": UUID2}]}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "(id = $1) OR (owner_id = $2)"; assert params == [UUID1, UUID2]
    def test_simple_metadata_equality_implicit(self):
        filters = {"key": "value"}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        expected_sql = f"{self.json_column}->>'key'=$1"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == ["value"]
    def test_simple_metadata_equality_explicit(self):
        filters = {"metadata.key": "value"}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        expected_sql = f"{self.json_column}->>'key'=$1"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == ["value"]
    def test_numeric_metadata_comparison_implicit(self):
        filters = {"score": {FilterOperator.GT: 50}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        accessor = f"{self.json_column}->>'score'"; expected_sql = self._expected_safe_compare_sql(accessor, '>', '$1', 'numeric')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == [50]
    def test_numeric_metadata_comparison_explicit(self):
        filters = {"metadata.score": {FilterOperator.GT: 50}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        accessor = f"{self.json_column}->>'score'"; expected_sql = self._expected_safe_compare_sql(accessor, '>', '$1', 'numeric')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == [50]
    def test_metadata_column_target_nested(self):
        filters = {self.json_column: {"path.to.value": {FilterOperator.EQ: 10}}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        accessor = f"{self.json_column}#>>'{{\"path\",\"to\",\"value\"}}'"
        expected_sql = self._expected_safe_compare_sql(accessor, '=', '$1', 'numeric')
        assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == [10]
    def test_collection_id_shorthand(self):
        filters = {"collection_id": UUID1}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql.replace(" ", "") == "collection_ids&&ARRAY[$1]::uuid[]"; assert params == [UUID1]
    def test_collection_ids_overlap(self):
        filters = {"collection_ids": {FilterOperator.OVERLAP: [UUID1, UUID2]}}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql.replace(" ", "") == "collection_ids&&ARRAY[$1,$2]::uuid[]"; assert params == [UUID1, UUID2]
    def test_collection_ids_array_contains(self):
        filters = {"collection_ids": {FilterOperator.ARRAY_CONTAINS: [UUID1, UUID2]}}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql.replace(" ", "") == "collection_ids@>ARRAY[$1,$2]::uuid[]"; assert params == [UUID1, UUID2]
    def test_empty_filters_condition_mode(self):
        sql, params = apply_filters({}, [], mode="condition_only"); assert sql == "TRUE"; assert params == []
    def test_empty_filters_where_mode(self):
        sql, params = apply_filters({}, [], mode="where_clause"); assert sql == ""; assert params == []
    def test_false_filters_where_mode(self):
        filters = {"id": {FilterOperator.IN: []}}; sql, params = apply_filters(filters, [], mode="where_clause")
        assert sql == "WHERE FALSE"; assert params == []
    def test_null_value_standard(self):
        filters = {"owner_id": None}; sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "owner_id IS NULL"; assert params == []
    def test_initial_params_accumulation(self):
         initial = ["initial_param"]; filters = {"id": UUID1}; sql, params = apply_filters(filters, param_list=initial, mode="condition_only")
         assert sql == "id = $2"; assert params == ["initial_param", UUID1]
    def test_custom_top_level_columns(self):
        custom_columns = {"id", "custom_field"}; filters_meta = {"other_field": "value"}; sql_m, params_m = apply_filters(filters_meta, [], top_level_columns=custom_columns, mode="condition_only")
        assert f"{self.json_column}->>'other_field'=$1" == sql_m.replace(" ", ""); assert params_m == ["value"]; filters_custom = {"custom_field": 123}
        sql_c, params_c = apply_filters(filters_custom, [], top_level_columns=custom_columns, mode="condition_only")
        assert "custom_field=$1" == sql_c.replace(" ", ""); assert params_c == [123]
    def test_custom_json_column(self):
        custom_json = "properties"; filters = {"field": "value"}; sql, params = apply_filters(filters, [], top_level_columns=["id"], json_column=custom_json, mode="condition_only")
        assert f"{custom_json}->>'field'=$1" == sql.replace(" ", ""); assert params == ["value"]
    def test_metadata_array_in_implicit(self):
        filters = {"tags": {FilterOperator.IN: ["urgent", "new"]}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        expected_sql = f"{self.json_column}->'tags' ?| ARRAY[$1,$2]::text[]"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == ["urgent", "new"]
    def test_metadata_array_in_explicit_nested(self):
        filters = {f"{self.json_column}.version_info.tags": {FilterOperator.IN: ["legacy"]}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        expected_sql = f"{self.json_column}#>'{{\"version_info\",\"tags\"}}' ?| ARRAY[$1]::text[]"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == ["legacy"]
    def test_metadata_array_nin_implicit(self):
        filters = {"tags": {FilterOperator.NIN: ["obsolete"]}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        expected_sql = f"NOT ({self.json_column}->'tags' ?| ARRAY[$1]::text[])"; assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == ["obsolete"]
    # --- CORRECTED test_metadata_array_nin_explicit_nested ---
    def test_metadata_array_nin_explicit_nested(self):
        filters = {f"{self.json_column}.options": {FilterOperator.NIN: ["disabled", "hidden"]}}
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        # Corrected Expectation: Uses -> for single segment path 'options'
        expected_sql = f"NOT ({self.json_column}->'options' ?| ARRAY[$1,$2]::text[])"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert params == ["disabled", "hidden"]
    def test_metadata_array_in_empty(self):
        filters = {"tags": {FilterOperator.IN: []}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        assert sql == "FALSE"; assert params == []
    def test_metadata_array_nin_empty(self):
        filters = {"tags": {FilterOperator.NIN: []}}; sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        assert sql == "TRUE"; assert params == []
    def test_combined_filters(self):
        filters = { FilterOperator.AND: [ {"id": UUID1}, {f"{self.json_column}.score": {FilterOperator.GTE: 80}}, {FilterOperator.OR: [{"collection_id": UUID2}, {"owner_id": {FilterOperator.EQ: UUID3}}]} ] }
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column); accessor = f"{self.json_column}->>'score'"
        score_condition = self._expected_safe_compare_sql(accessor, '>=', '$2', 'numeric'); expected_sql = ( f"(id = $1) AND ({score_condition}) AND ((collection_ids && ARRAY[$3]::uuid[]) OR (owner_id = $4))" )
        assert sql.replace(" ","") == expected_sql.replace(" ",""); assert params == [UUID1, 80, UUID2, UUID3]
    def test_combined_filters_with_array_in(self):
         filters = { FilterOperator.AND: [ {"id": UUID1}, {f"{self.json_column}.labels": {FilterOperator.IN: ["critical"]}}, {FilterOperator.OR: [{"collection_id": UUID2}, {"owner_id": {FilterOperator.EQ: UUID3}}]} ] }
         sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column); labels_condition = f"{self.json_column}->'labels' ?| ARRAY[$2]::text[]"
         expected_sql = ( f"(id = $1) AND ({labels_condition}) AND ((collection_ids && ARRAY[$3]::uuid[]) OR (owner_id = $4))" )
         assert sql.replace(" ","") == expected_sql.replace(" ",""); assert params == [UUID1, "critical", UUID2, UUID3]
    def test_more_complex_metadata_and_standard(self):
         filters = { "status": {FilterOperator.NE: "archived"}, "metadata.tags": {FilterOperator.JSON_CONTAINS: ["urgent"]}, FilterOperator.OR: [ {f"{self.json_column}.priority": {FilterOperator.GTE: 5}}, {"owner_id": UUID1} ] }
         sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column); tags_condition = f"{self.json_column}->'tags' @> $2::jsonb"
         accessor = f"{self.json_column}->>'priority'"; priority_condition = self._expected_safe_compare_sql(accessor, '>=', '$3', 'numeric')
         expected_sql = ( f"(status!=$1) AND ({tags_condition}) AND (({priority_condition}) OR (owner_id = $4))" )
         assert sql.replace(" ", "") == expected_sql.replace(" ", ""); assert params == ["archived", json.dumps(["urgent"]), 5, UUID1]
