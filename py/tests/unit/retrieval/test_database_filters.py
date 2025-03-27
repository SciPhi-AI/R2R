import json
import pytest
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Add sys.path manipulation to help Python find the modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the filter implementation components directly
from core.providers.database.filters import (
    FilterError,
    FilterOperator,
    ParamHelper, # Import the helper class
    apply_filters,
    DEFAULT_TOP_LEVEL_COLUMNS,
    _process_filter_dict,
    _process_field_condition,
    _build_standard_column_condition,
    _build_collection_ids_condition,
    _build_metadata_condition, # This is the main entry point now
    _build_metadata_operator_condition, # We might test this directly too for granularity
)

# Define some test UUIDs
UUID1 = str(uuid.uuid4())
UUID2 = str(uuid.uuid4())
UUID3 = str(uuid.uuid4())

# Default JSON column name used in tests
JSON_COLUMN = "metadata"

# Default top-level columns for testing internal functions
TEST_TOP_LEVEL_COLS = DEFAULT_TOP_LEVEL_COLUMNS.copy()


# --- Unit Tests for Internal Helper Functions ---

class TestParamHelper:
    """Tests for the ParamHelper class."""
    def test_initialization_empty(self):
        helper = ParamHelper()
        assert helper.params == []
        assert helper.index == 1

    def test_initialization_with_params(self):
        initial = ["param0"]
        helper = ParamHelper(initial)
        assert helper.params == initial
        assert helper.index == 2 # Starts at len + 1

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
        ph3 = helper.add(None) # None is added as a parameter value
        assert ph2 == "$2"
        assert ph3 == "$3"
        assert helper.params == [True, "abc", None]
        assert helper.index == 4

class TestBuildStandardColumnCondition:
    """Tests for _build_standard_column_condition."""

    @pytest.mark.parametrize("op, value, expected_sql, expected_params", [
        (FilterOperator.EQ, "val", "col = $1", ["val"]),
        (FilterOperator.EQ, 123, "col = $1", [123]),
        (FilterOperator.EQ, None, "col IS NULL", []),
        (FilterOperator.NE, "val", "col != $1", ["val"]),
        (FilterOperator.NE, None, "col IS NOT NULL", []),
        (FilterOperator.GT, 10, "col > $1", [10]),
        (FilterOperator.GTE, 10, "col >= $1", [10]),
        (FilterOperator.LT, 10, "col < $1", [10]),
        (FilterOperator.LTE, 10, "col <= $1", [10]),
        (FilterOperator.LIKE, "%pattern%", "col LIKE $1", ["%pattern%"]),
        (FilterOperator.ILIKE, "%pattern%", "col ILIKE $1", ["%pattern%"]),
        # List operators
        (FilterOperator.IN, ["a", "b"], "col IN ($1, $2)", ["a", "b"]),
        (FilterOperator.IN, [], "FALSE", []), # Empty IN is FALSE
        (FilterOperator.NIN, ["a", "b"], "col NOT IN ($1, $2)", ["a", "b"]),
        (FilterOperator.NIN, [], "TRUE", []), # Empty NIN is TRUE
    ])
    def test_operators(self, op, value, expected_sql, expected_params):
        helper = ParamHelper()
        sql = _build_standard_column_condition("col", op, value, helper)
        assert sql == expected_sql
        assert helper.params == expected_params

    def test_unsupported_operator(self):
        helper = ParamHelper()
        with pytest.raises(FilterError, match="Unsupported operator"):
            _build_standard_column_condition("col", FilterOperator.OVERLAP, [], helper) # Overlap invalid for standard

    def test_invalid_value_type_for_like(self):
        helper = ParamHelper()
        with pytest.raises(FilterError, match="requires a string value"):
            _build_standard_column_condition("col", FilterOperator.LIKE, 123, helper)
        with pytest.raises(FilterError, match="requires a string value"):
            _build_standard_column_condition("col", FilterOperator.ILIKE, 123, helper)

    def test_invalid_value_type_for_list_ops(self):
        helper = ParamHelper()
        with pytest.raises(FilterError, match="requires a list value"):
            _build_standard_column_condition("col", FilterOperator.IN, "not-a-list", helper)
        with pytest.raises(FilterError, match="requires a list value"):
            _build_standard_column_condition("col", FilterOperator.NIN, "not-a-list", helper)


class TestBuildCollectionIdsCondition:
    """Tests for _build_collection_ids_condition."""

    @pytest.mark.parametrize("op, value, expected_sql, expected_params", [
        # OVERLAP / IN (Mapped to &&)
        (FilterOperator.OVERLAP, [UUID1], "collection_ids && ARRAY[$1]::uuid[]", [UUID1]),
        (FilterOperator.OVERLAP, [UUID1, UUID2], "collection_ids && ARRAY[$1,$2]::uuid[]", [UUID1, UUID2]),
        (FilterOperator.IN, [UUID1, UUID2], "collection_ids && ARRAY[$1,$2]::uuid[]", [UUID1, UUID2]),
        (FilterOperator.OVERLAP, [], "FALSE", []),
        (FilterOperator.IN, [], "FALSE", []),
        # ARRAY_CONTAINS (@>)
        (FilterOperator.ARRAY_CONTAINS, [UUID1], "collection_ids @> ARRAY[$1]::uuid[]", [UUID1]),
        (FilterOperator.ARRAY_CONTAINS, [UUID1, UUID2], "collection_ids @> ARRAY[$1,$2]::uuid[]", [UUID1, UUID2]),
        (FilterOperator.ARRAY_CONTAINS, [], "TRUE", []), # Contains all of empty set
        # NIN (NOT &&)
        (FilterOperator.NIN, [UUID1], "NOT (collection_ids && ARRAY[$1]::uuid[])", [UUID1]),
        (FilterOperator.NIN, [UUID1, UUID2], "NOT (collection_ids && ARRAY[$1,$2]::uuid[])", [UUID1, UUID2]),
        (FilterOperator.NIN, [], "TRUE", []),
        # EQ (Exact array match - rare)
        (FilterOperator.EQ, UUID1, "collection_ids = ARRAY[$1]::uuid[]", [UUID1]),
        # NE (Exact array non-match - rare)
        (FilterOperator.NE, UUID1, "collection_ids != ARRAY[$1]::uuid[]", [UUID1]),
    ])
    def test_operators(self, op, value, expected_sql, expected_params):
        helper = ParamHelper()
        # Test calling with 'collection_ids' as field name
        sql_direct = _build_collection_ids_condition("collection_ids", op, value, helper)
        assert sql_direct.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == expected_params


    def test_invalid_uuid(self):
        helper = ParamHelper()
        with pytest.raises(FilterError, match="Invalid UUID format"):
            _build_collection_ids_condition("collection_ids", FilterOperator.OVERLAP, ["invalid"], helper)
        with pytest.raises(FilterError, match="Invalid UUID format"):
            _build_collection_ids_condition("collection_ids", FilterOperator.ARRAY_CONTAINS, [UUID1, "invalid"], helper)
        with pytest.raises(FilterError, match="Invalid UUID format"):
            _build_collection_ids_condition("collection_ids", FilterOperator.EQ, "invalid", helper) # Single value EQ

    def test_invalid_value_type_list(self):
        helper = ParamHelper()
        with pytest.raises(FilterError, match="requires a list"):
            _build_collection_ids_condition("collection_ids", FilterOperator.OVERLAP, UUID1, helper) # Needs list
        with pytest.raises(FilterError, match="requires a list"):
            _build_collection_ids_condition("collection_ids", FilterOperator.ARRAY_CONTAINS, UUID1, helper) # Needs list

    def test_invalid_value_type_single(self):
         helper = ParamHelper()
         with pytest.raises(FilterError, match="requires a single UUID"):
             _build_collection_ids_condition("collection_ids", FilterOperator.EQ, [UUID1], helper) # Needs single
         with pytest.raises(FilterError, match="requires a single UUID"):
             _build_collection_ids_condition("collection_ids", FilterOperator.NE, [UUID1], helper) # Needs single

    def test_unsupported_operator(self):
        helper = ParamHelper()
        with pytest.raises(FilterError, match="Unsupported operator"):
            _build_collection_ids_condition("collection_ids", FilterOperator.GT, [UUID1], helper) # GT invalid


class TestBuildMetadataCondition:
    """
    Tests for _build_metadata_condition (main entry point) and indirectly
    _build_metadata_operator_condition.
    """
    json_col = JSON_COLUMN

    @pytest.mark.parametrize("op, value, expected_sql_part, expected_params", [
        # EQ (Shorthand test handled below)
        (FilterOperator.EQ, "val", f"->>'key' = $1", ["val"]),
        (FilterOperator.EQ, 123, f"->>'key')::numeric = $1", [123]),
        (FilterOperator.EQ, True, f"->>'key')::boolean = $1", [True]),
        # NE
        (FilterOperator.NE, "val", f"->>'key' != $1", ["val"]),
        (FilterOperator.NE, 123, f"->>'key')::numeric != $1", [123]),
        (FilterOperator.NE, False, f"->>'key')::boolean != $1", [False]),
        # Comparisons (numeric)
        (FilterOperator.GT, 10, f"->>'key')::numeric > $1", [10]),
        (FilterOperator.GTE, 10.5, f"->>'key')::numeric >= $1", [10.5]),
        (FilterOperator.LT, 10, f"->>'key')::numeric < $1", [10]),
        (FilterOperator.LTE, 10.5, f"->>'key')::numeric <= $1", [10.5]),
         # Comparisons (text - less common but should work)
        (FilterOperator.GT, "abc", f"->>'key' > $1", ["abc"]),
        # String matching
        (FilterOperator.LIKE, "%pat%", f"->>'key' LIKE $1", ["%pat%"]),
        (FilterOperator.ILIKE, "%pat%", f"->>'key' ILIKE $1", ["%pat%"]),
        # IN / NIN (text based)
        (FilterOperator.IN, ["a", "b"], f"->>'key') IN ($1, $2)", ["a", "b"]), # Note added parens around accessor
        (FilterOperator.IN, [], "FALSE", []),
        (FilterOperator.NIN, ["a", "b"], f"->>'key') NOT IN ($1, $2)", ["a", "b"]), # Note added parens around accessor
        (FilterOperator.NIN, [], "TRUE", []),
        # JSON Contains (uses -> and @>)
        (FilterOperator.JSON_CONTAINS, {"a": 1}, f"->'key' @> $1::jsonb", [json.dumps({"a": 1})]),
        (FilterOperator.JSON_CONTAINS, ["a", 1], f"->'key' @> $1::jsonb", [json.dumps(["a", 1])]),
        (FilterOperator.JSON_CONTAINS, "scalar", f"->'key' @> $1::jsonb", [json.dumps("scalar")]),
    ])
    def test_operators_simple_path(self, op, value, expected_sql_part, expected_params):
        """Tests applying operators directly to a top-level metadata key."""
        helper = ParamHelper()
        # Construct the condition_spec dictionary {op: value}
        condition_spec = {op: value}
        # Call the main function with relative_path="key"
        sql = _build_metadata_condition("key", condition_spec, helper, self.json_col)

        # Construct expected SQL structure carefully
        expected_sql_full = ""
        if value == [] and op in [FilterOperator.IN]:
            expected_sql_full = "FALSE"
        elif value == [] and op in [FilterOperator.NIN]:
             expected_sql_full = "TRUE"
        elif op == FilterOperator.JSON_CONTAINS:
             expected_sql_full = f"{self.json_col}{expected_sql_part}"
        elif "::numeric" in expected_sql_part or "::boolean" in expected_sql_part:
             # Cast operations need parens around the accessor+cast
             expected_sql_full = f"({self.json_col}{expected_sql_part}"
        elif op in [FilterOperator.IN, FilterOperator.NIN]:
             # IN/NIN need parens around accessor
             expected_sql_full = f"({self.json_col}{expected_sql_part}"
        else: # Simple scalar comparisons or LIKE
             expected_sql_full = f"{self.json_col}{expected_sql_part}"

        # Use exact match (ignoring spaces)
        assert sql.replace(" ", "") == expected_sql_full.replace(" ", "")
        assert helper.params == expected_params

    def test_eq_shorthand_simple_path(self):
        """Tests the shorthand { "key": "value" } mapping to EQ."""
        helper = ParamHelper()
        condition_spec = "value" # Shorthand for EQ
        sql = _build_metadata_condition("key", condition_spec, helper, self.json_col)
        expected_sql = f"{self.json_col}->>'key' = $1"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == ["value"]


    @pytest.mark.parametrize("op, value, expected_sql_part, expected_params", [
        # EQ (Shorthand tested below)
        (FilterOperator.EQ, "val", f"#>>'{{p1,p2}}' = $1", ["val"]),
        (FilterOperator.EQ, 123, f"#>>'{{p1,p2}}')::numeric = $1", [123]),
        # Comparisons (numeric)
        (FilterOperator.LT, 0, f"#>>'{{p1,p2}}')::numeric < $1", [0]),
        # IN / NIN (text based)
        (FilterOperator.IN, ["x"], f"#>>'{{p1,p2}}') IN ($1)", ["x"]), # Note added parens
        # JSON Contains (uses #> and @>)
        (FilterOperator.JSON_CONTAINS, {"c": True}, f"#>'{{p1,p2}}' @> $1::jsonb", [json.dumps({"c": True})]),
    ])
    def test_operators_nested_path(self, op, value, expected_sql_part, expected_params):
        """Tests applying operators directly to a nested metadata key "p1.p2"."""
        helper = ParamHelper()
        condition_spec = {op: value}
        sql = _build_metadata_condition("p1.p2", condition_spec, helper, self.json_col)

        # Construct expected SQL structure carefully
        expected_sql_full = ""
        if op == FilterOperator.JSON_CONTAINS:
             expected_sql_full = f"{self.json_col}{expected_sql_part}"
        elif "::numeric" in expected_sql_part or "::boolean" in expected_sql_part:
             expected_sql_full = f"({self.json_col}{expected_sql_part}"
        elif op in [FilterOperator.IN, FilterOperator.NIN]:
             expected_sql_full = f"({self.json_col}{expected_sql_part}"
        else:
             expected_sql_full = f"{self.json_col}{expected_sql_part}"

        assert sql.replace(" ", "") == expected_sql_full.replace(" ", "")
        assert helper.params == expected_params

    def test_eq_shorthand_nested_path(self):
        """Tests the shorthand { "p1.p2": "value" } mapping to EQ."""
        helper = ParamHelper()
        condition_spec = "value" # Shorthand for EQ
        sql = _build_metadata_condition("p1.p2", condition_spec, helper, self.json_col)
        expected_sql = f"{self.json_col}#>>'{{p1,p2}}' = $1"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == ["value"]

    def test_nested_structure_condition(self):
        """Tests condition like {"p1": {"p2": "value"}}"""
        helper = ParamHelper()
        condition_spec = {"p2": "value"} # Nested condition
        sql = _build_metadata_condition("p1", condition_spec, helper, self.json_col)
        # Expects recursion to handle p1.p2 with EQ
        expected_sql = f"{self.json_col}#>>'{{p1,p2}}' = $1"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == ["value"]

    def test_nested_structure_condition_with_op(self):
        """Tests condition like {"p1": {"p2": {"$gt": 5}}}"""
        helper = ParamHelper()
        condition_spec = {"p2": {FilterOperator.GT: 5}} # Nested condition with operator
        sql = _build_metadata_condition("p1", condition_spec, helper, self.json_col)
        # Expects recursion to handle p1.p2 with GT
        expected_sql = f"({self.json_col}#>>'{{p1,p2}}')::numeric > $1"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == [5]


    def test_null_handling_simple(self):
        """Tests null comparison for top-level metadata key."""
        helper_eq = ParamHelper()
        condition_spec_eq = {FilterOperator.EQ: None}
        sql_eq = _build_metadata_condition("key", condition_spec_eq, helper_eq, self.json_col)
        # Check the full structure for NULL EQ
        expected_sql_eq = f"({self.json_col}->'key' IS NOT NULL AND {self.json_col}->'key' = 'null'::jsonb)"
        assert sql_eq.replace(" ", "") == expected_sql_eq.replace(" ","")
        assert helper_eq.params == []

        helper_ne = ParamHelper()
        condition_spec_ne = {FilterOperator.NE: None}
        sql_ne = _build_metadata_condition("key", condition_spec_ne, helper_ne, self.json_col)
        # Check the full structure for NULL NE
        expected_sql_ne = f"({self.json_col}->'key' IS NULL OR {self.json_col}->'key' != 'null'::jsonb)"
        assert sql_ne.replace(" ", "") == expected_sql_ne.replace(" ","")
        assert helper_ne.params == []

    def test_null_handling_nested(self):
        """Tests null comparison for nested metadata key "p1.p2"."""
        helper_eq = ParamHelper()
        condition_spec_eq = {FilterOperator.EQ: None}
        sql_eq = _build_metadata_condition("p1.p2", condition_spec_eq, helper_eq, self.json_col)
        # Check the full structure for NULL EQ (nested)
        expected_sql_eq = f"({self.json_col}#>'{'{p1,p2}'}' IS NOT NULL AND {self.json_col}#>'{'{p1,p2}'}' = 'null'::jsonb)"
        assert sql_eq.replace(" ", "") == expected_sql_eq.replace(" ","")
        assert helper_eq.params == []

        helper_ne = ParamHelper()
        condition_spec_ne = {FilterOperator.NE: None}
        sql_ne = _build_metadata_condition("p1.p2", condition_spec_ne, helper_ne, self.json_col)
        # Check the full structure for NULL NE (nested)
        expected_sql_ne = f"({self.json_col}#>'{'{p1,p2}'}' IS NULL OR {self.json_col}#>'{'{p1,p2}'}' != 'null'::jsonb)"
        assert sql_ne.replace(" ", "") == expected_sql_ne.replace(" ","")
        assert helper_ne.params == []


    def test_unsupported_operator(self):
        helper = ParamHelper()
        condition_spec = {FilterOperator.OVERLAP: []} # Invalid op for metadata
        with pytest.raises(FilterError, match="Unsupported operator"):
            _build_metadata_condition("key", condition_spec, helper, self.json_col)

    def test_json_contains_non_serializable(self):
        helper = ParamHelper()
        condition_spec = {FilterOperator.JSON_CONTAINS: {"a": {1, 2}}} # Set is not serializable
        with pytest.raises(FilterError, match="must be JSON serializable"):
             _build_metadata_condition("key", condition_spec, helper, self.json_col)


class TestProcessFieldCondition:
    """Tests for _process_field_condition (routing logic)."""
    # This tests that the correct builder/processing logic is called based on field name/type

    top_cols = TEST_TOP_LEVEL_COLS
    json_col = JSON_COLUMN

    def test_routes_collection_id_shorthand_single_value(self):
        helper = ParamHelper()
        sql = _process_field_condition("collection_id", UUID1, helper, self.top_cols, self.json_col)
        # Expect it called _build_collection_ids_condition with OVERLAP
        assert "collection_ids&&ARRAY[$1]::uuid[]" == sql.replace(" ","")
        assert helper.params == [UUID1]

    def test_routes_collection_id_shorthand_eq_op(self):
        helper = ParamHelper()
        sql = _process_field_condition("collection_id", {FilterOperator.EQ: UUID1}, helper, self.top_cols, self.json_col)
         # Expect EQ shorthand maps to OVERLAP
        assert "collection_ids&&ARRAY[$1]::uuid[]" == sql.replace(" ","")
        assert helper.params == [UUID1]

    def test_routes_collection_id_shorthand_ne_op(self):
        helper = ParamHelper()
        sql = _process_field_condition("collection_id", {FilterOperator.NE: UUID1}, helper, self.top_cols, self.json_col)
         # Expect NE shorthand maps to NOT &&
        assert "NOT(collection_ids&&ARRAY[$1]::uuid[])" == sql.replace(" ","")
        assert helper.params == [UUID1]

    def test_routes_collection_id_shorthand_in_op(self):
        helper = ParamHelper()
        sql = _process_field_condition("collection_id", {FilterOperator.IN: [UUID1, UUID2]}, helper, self.top_cols, self.json_col)
         # Expect IN is passed correctly (maps to &&)
        assert "collection_ids&&ARRAY[$1,$2]::uuid[]" == sql.replace(" ","")
        assert helper.params == [UUID1, UUID2]

    def test_routes_collection_ids_direct_op(self):
        helper = ParamHelper()
        sql = _process_field_condition("collection_ids", {FilterOperator.OVERLAP: [UUID1, UUID2]}, helper, self.top_cols, self.json_col)
        # Expect it called _build_collection_ids_condition directly
        assert "collection_ids&&ARRAY[$1,$2]::uuid[]" == sql.replace(" ","")
        assert helper.params == [UUID1, UUID2]

    def test_routes_collection_ids_shorthand_list(self):
         helper = ParamHelper()
         sql = _process_field_condition("collection_ids", [UUID1, UUID2], helper, self.top_cols, self.json_col)
         # Expect list shorthand maps to OVERLAP
         assert "collection_ids&&ARRAY[$1,$2]::uuid[]" == sql.replace(" ","")
         assert helper.params == [UUID1, UUID2]

    def test_routes_standard_column_shorthand_eq(self):
        helper = ParamHelper()
        sql = _process_field_condition("owner_id", UUID1, helper, self.top_cols, self.json_col)
        # Expect it called _build_standard_column_condition
        assert "owner_id=$1" == sql.replace(" ", "")
        assert helper.params == [UUID1]

    def test_routes_standard_column_op(self):
        helper = ParamHelper()
        sql = _process_field_condition("status", {FilterOperator.NE: "active"}, helper, self.top_cols, self.json_col)
         # Expect it called _build_standard_column_condition
        assert "status != $1" == sql.replace(" ", "")
        assert helper.params == ["active"]

    # --- Metadata Routing Tests ---
    def test_routes_metadata_shorthand_eq_implicit(self):
        """Field name 'tags' is not top-level -> assumed metadata"""
        helper = ParamHelper()
        sql = _process_field_condition("tags", "urgent", helper, self.top_cols, json_column=self.json_col)
        # Expect it called _build_metadata_condition -> operator_condition with EQ
        assert f"{self.json_col}->>'tags'=$1" == sql.replace(" ", "")
        assert helper.params == ["urgent"]

    def test_routes_metadata_op_implicit(self):
        """Field name 'score' is not top-level -> assumed metadata"""
        helper = ParamHelper()
        sql = _process_field_condition("score", {FilterOperator.GT: 90}, helper, self.top_cols, self.json_col)
        # Expect it called _build_metadata_condition -> operator_condition with GT
        assert f"({self.json_col}->>'score')::numeric>$1" == sql.replace(" ", "")
        assert helper.params == [90]

    def test_routes_metadata_nested_shorthand_eq_implicit(self):
        """Field name 'nested.value' is not top-level -> assumed metadata path"""
        helper = ParamHelper()
        sql = _process_field_condition("nested.value", True, helper, self.top_cols, self.json_col)
        # Expect it called _build_metadata_condition -> operator_condition with EQ on nested path
        assert f"({self.json_col}#>>'{{nested,value}}')::boolean=$1" == sql.replace(" ", "")
        assert helper.params == [True]

    def test_routes_metadata_nested_structure_implicit(self):
        """Field 'nested' is not top-level; value is dict -> assume nested structure"""
        helper = ParamHelper()
        sql = _process_field_condition("nested", {"value": True}, helper, self.top_cols, self.json_col)
        # Expect it processes recursively to "nested.value" with EQ
        assert f"({self.json_col}#>>'{{nested,value}}')::boolean=$1" == sql.replace(" ", "")
        assert helper.params == [True]

    def test_routes_metadata_nested_structure_op_implicit(self):
        """Field 'nested' is not top-level; value is dict with op -> assume nested structure"""
        helper = ParamHelper()
        sql = _process_field_condition("nested", {"value": {FilterOperator.GT: 5}}, helper, self.top_cols, self.json_col)
        # Expect it processes recursively to "nested.value" with GT
        assert f"({self.json_col}#>>'{{nested,value}}')::numeric>$1" == sql.replace(" ", "")
        assert helper.params == [5]

    def test_routes_metadata_explicit_path_shorthand(self):
        """Field name 'metadata.key' explicitly targets json column"""
        helper = ParamHelper()
        sql = _process_field_condition(f"{self.json_col}.key", "value", helper, self.top_cols, json_column=self.json_col)
        # Expect it routes to _build_metadata_condition with relative_path="key" and EQ
        assert f"{self.json_col}->>'key'=$1" == sql.replace(" ", "")
        assert helper.params == ["value"]

    def test_routes_metadata_explicit_path_op(self):
        """Field name 'metadata.key' explicitly targets json column with operator"""
        helper = ParamHelper()
        sql = _process_field_condition(f"{self.json_col}.score", {FilterOperator.LTE: 100}, helper, self.top_cols, json_column=self.json_col)
         # Expect it routes to _build_metadata_condition with relative_path="score" and LTE
        assert f"({self.json_col}->>'score')::numeric<=$1" == sql.replace(" ", "")
        assert helper.params == [100]

    def test_routes_metadata_explicit_column_nested_structure(self):
        """Field name is 'metadata', value is dict -> process nested structure"""
        helper = ParamHelper()
        condition_spec = {"path.to.key": "val", "another": {FilterOperator.NE: False}}
        sql = _process_field_condition(self.json_col, condition_spec, helper, self.top_cols, json_column=self.json_col)
        # Expect processing of both conditions inside 'metadata' column, joined by AND
        expected_part1 = f"{self.json_col}#>>'{{path,to,key}}'=$1"
        expected_part2 = f"({self.json_col}->>'another')::boolean!=$2"
        expected_sql = f"({expected_part1})AND({expected_part2})"
        assert sql.replace(" ", "") == expected_sql.replace(" ", "")
        assert helper.params == ["val", False]


class TestProcessFilterDict:
    """Tests for _process_filter_dict (recursion, logical ops)."""

    top_cols = TEST_TOP_LEVEL_COLS
    json_col = JSON_COLUMN

    def test_empty_dict(self):
        helper = ParamHelper()
        sql = _process_filter_dict({}, helper, self.top_cols, self.json_col)
        assert sql == "TRUE"
        assert helper.params == []

    def test_single_field_condition(self):
        helper = ParamHelper()
        filters = {"id": UUID1}
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "id = $1"
        assert helper.params == [UUID1]

    def test_multiple_field_conditions_implicit_and(self):
        helper = ParamHelper()
        filters = {"id": UUID1, "status": "active"}
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        # Check exact structure (implicit AND with parens around each)
        # Order might vary, so check both possibilities
        expected_sql1 = "(id = $1) AND (status = $2)"
        expected_sql2 = "(status = $1) AND (id = $2)"
        actual_sql = sql.replace(" ","")
        assert actual_sql == expected_sql1.replace(" ","") or actual_sql == expected_sql2.replace(" ","")
        assert set(helper.params) == {UUID1, "active"}

    def test_logical_and(self):
        helper = ParamHelper()
        filters = {FilterOperator.AND: [{"id": UUID1}, {"status": "active"}]}
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        # Parens around each sub-condition from the list, joined by AND
        assert sql == "(id = $1) AND (status = $2)"
        assert helper.params == [UUID1, "active"]

    def test_logical_or(self):
        helper = ParamHelper()
        filters = {FilterOperator.OR: [{"id": UUID1}, {"status": "active"}]}
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
         # Parens around each sub-condition from the list, joined by OR
        assert sql == "(id = $1) OR (status = $2)"
        assert helper.params == [UUID1, "active"]

    def test_nested_logical(self):
        helper = ParamHelper()
        filters = {
            FilterOperator.AND: [
                {"id": UUID1},
                {FilterOperator.OR: [{"status": "active"}, {"score": {FilterOperator.GT: 90}}]}
            ]
        }
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        # Check exact structure (ignoring spaces)
        # Outer AND joins two parts: (id=$1) and the OR clause
        # Inner OR joins two parts: (status=$2) and the score comparison
        expected_sql = \
           f"(id = $1) AND ((status = $2) OR (({self.json_col}->>'score')::numeric > $3))"
        assert sql.replace(" ","") == expected_sql.replace(" ","")
        assert helper.params == [UUID1, "active", 90]

    def test_empty_logical_and(self):
        helper = ParamHelper()
        filters = {FilterOperator.AND: []}
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "TRUE" # Empty AND is TRUE
        assert helper.params == []

    def test_empty_logical_or(self):
        helper = ParamHelper()
        filters = {FilterOperator.OR: []}
        sql = _process_filter_dict(filters, helper, self.top_cols, self.json_col)
        assert sql == "FALSE" # Empty OR is FALSE
        assert helper.params == []


# --- Tests for the Public API (apply_filters) ---

class TestApplyFiltersApi:
    """Tests focusing on the public apply_filters function and its modes."""

    json_column = JSON_COLUMN

    # --- Basic Operations ---
    def test_simple_equality_filter(self):
        filters = {"id": UUID1}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "id = $1"
        assert params == [UUID1]

    def test_operator_equality_filter(self):
        filters = {"id": {FilterOperator.EQ: UUID1}}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "id = $1"
        assert params == [UUID1]

    # --- Logical Operators ---
    def test_and_operator(self):
        filters = {FilterOperator.AND: [{"id": UUID1}, {"owner_id": UUID2}]}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "(id = $1) AND (owner_id = $2)"
        assert params == [UUID1, UUID2]

    def test_or_operator(self):
        filters = {FilterOperator.OR: [{"id": UUID1}, {"owner_id": UUID2}]}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "(id = $1) OR (owner_id = $2)"
        assert params == [UUID1, UUID2]

    # --- Metadata ---
    def test_simple_metadata_equality_implicit(self):
        """'key' is assumed metadata field"""
        filters = {"key": "value"}
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        assert sql.replace(" ", "") == f"{self.json_column}->>'key'=$1".replace(" ", "")
        assert params == ["value"]

    def test_simple_metadata_equality_explicit(self):
        """'metadata.key' explicitly targets metadata"""
        filters = {"metadata.key": "value"}
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        assert sql.replace(" ", "") == f"{self.json_column}->>'key'=$1".replace(" ", "")
        assert params == ["value"]

    def test_numeric_metadata_comparison_implicit(self):
        filters = {"score": {FilterOperator.GT: 50}}
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        assert sql.replace(" ", "") == f"({self.json_column}->>'score')::numeric>$1".replace(" ", "")
        assert params == [50]

    def test_numeric_metadata_comparison_explicit(self):
        filters = {"metadata.score": {FilterOperator.GT: 50}}
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        assert sql.replace(" ", "") == f"({self.json_column}->>'score')::numeric>$1".replace(" ", "")
        assert params == [50]

    def test_metadata_column_target_nested(self):
        """Targeting 'metadata' column directly with nested path/op"""
        filters = {self.json_column: {"path.to.value": {FilterOperator.EQ: 10}}}
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        assert sql.replace(" ", "") == f"({self.json_column}#>>'{{path,to,value}}')::numeric=$1".replace(" ", "")
        assert params == [10]


    # --- Special Fields ---
    def test_collection_id_shorthand(self):
        filters = {"collection_id": UUID1}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql.replace(" ", "") == "collection_ids&&ARRAY[$1]::uuid[]"
        assert params == [UUID1]

    def test_collection_ids_overlap(self):
        filters = {"collection_ids": {FilterOperator.OVERLAP: [UUID1, UUID2]}}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql.replace(" ", "") == "collection_ids&&ARRAY[$1,$2]::uuid[]"
        assert params == [UUID1, UUID2]

    def test_collection_ids_array_contains(self):
        filters = {"collection_ids": {FilterOperator.ARRAY_CONTAINS: [UUID1, UUID2]}}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql.replace(" ", "") == "collection_ids@>ARRAY[$1,$2]::uuid[]"
        assert params == [UUID1, UUID2]

    # --- Edge Cases & Modes ---
    def test_empty_filters_condition_mode(self):
        sql, params = apply_filters({}, [], mode="condition_only")
        assert sql == "TRUE"
        assert params == []

    def test_empty_filters_where_mode(self):
        sql, params = apply_filters({}, [], mode="where_clause")
        assert sql == "" # WHERE TRUE becomes empty string
        assert params == []

    def test_false_filters_where_mode(self):
        filters = {"id": {FilterOperator.IN: []}} # Evaluates to FALSE
        sql, params = apply_filters(filters, [], mode="where_clause")
        assert sql == "WHERE FALSE"
        assert params == []

    def test_null_value_standard(self):
        filters = {"owner_id": None}
        sql, params = apply_filters(filters, [], mode="condition_only")
        assert sql == "owner_id IS NULL"
        assert params == []

    def test_initial_params_accumulation(self):
         initial = ["initial_param"]
         filters = {"id": UUID1}
         sql, params = apply_filters(filters, param_list=initial, mode="condition_only")
         assert sql == "id = $2" # Placeholder index starts after initial params
         assert params == ["initial_param", UUID1]

    def test_custom_top_level_columns(self):
        custom_columns = {"id", "custom_field"}
        # 'other_field' should be treated as metadata
        filters_meta = {"other_field": "value"}
        sql_m, params_m = apply_filters(filters_meta, [], top_level_columns=custom_columns, mode="condition_only")
        assert f"{self.json_column}->>'other_field'=$1" == sql_m.replace(" ", "")
        assert params_m == ["value"]
        # 'custom_field' should be treated as standard
        filters_custom = {"custom_field": 123}
        sql_c, params_c = apply_filters(filters_custom, [], top_level_columns=custom_columns, mode="condition_only")
        assert "custom_field=$1" == sql_c.replace(" ", "")
        assert params_c == [123]

    def test_custom_json_column(self):
        custom_json = "properties"
        filters = {"field": "value"} # Assume 'field' is within 'properties'
        sql, params = apply_filters(filters, [], top_level_columns=["id"], json_column=custom_json, mode="condition_only")
        assert f"{custom_json}->>'field'=$1" == sql.replace(" ", "")
        assert params == ["value"]

    # --- Complex ---
    def test_combined_filters(self):
        filters = {
            FilterOperator.AND: [
                {"id": UUID1},
                {f"{self.json_column}.score": {FilterOperator.GTE: 80}}, # Explicit metadata path
                {
                    FilterOperator.OR: [
                        {"collection_id": UUID2}, # Shorthand -> overlap
                        {"owner_id": {FilterOperator.EQ: UUID3}} # Standard column EQ
                    ]
                }
            ]
        }
        sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
        # Check exact structure (ignoring spaces)
        expected_sql = (
            f"(id = $1)"
            f" AND (({self.json_column}->>'score')::numeric >= $2)" # Metadata condition
            f" AND ((collection_ids && ARRAY[$3]::uuid[]) OR (owner_id = $4))" # OR clause
        )
        assert sql.replace(" ","") == expected_sql.replace(" ","")
        # Check params are in correct order
        assert params == [UUID1, 80, UUID2, UUID3]

    def test_more_complex_metadata_and_standard(self):
         filters = {
             "status": {FilterOperator.NE: "archived"}, # Standard column
             "metadata.tags": {FilterOperator.JSON_CONTAINS: ["urgent"]}, # Metadata JSONB contains
             FilterOperator.OR: [
                 {f"{self.json_column}.priority": {FilterOperator.GTE: 5}}, # Explicit metadata path numeric
                 {"owner_id": UUID1} # Standard column
             ]
         }
         sql, params = apply_filters(filters, [], mode="condition_only", json_column=self.json_column)
         expected_sql = (
             f"(status!=$1)"
             f" AND ({self.json_column}->'tags' @> $2::jsonb)" # JSON contains
             f" AND ((({self.json_column}->>'priority')::numeric >= $3) OR (owner_id = $4))" # OR clause
         )
         assert sql.replace(" ", "") == expected_sql.replace(" ", "")
         assert params == ["archived", json.dumps(["urgent"]), 5, UUID1]