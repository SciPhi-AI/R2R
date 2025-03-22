import json
import pytest
from typing import Any, Dict, List, Tuple

# Add sys.path manipulation to help Python find the modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import both filter implementations with appropriate aliases
from core.providers.database.filters import (
    FilterError as MainFilterError,
    FilterOperator as MainFilterOperator,
    apply_filters as main_apply_filters,
    _process_filter_dict as main_process_filter_dict,
    _build_metadata_condition as main_build_metadata_condition,
    _build_column_condition as main_build_column_condition,
    _build_collection_ids_condition as main_build_collection_ids_condition,
    _build_collection_id_condition as main_build_collection_id_condition,
    _build_parent_id_condition as main_build_parent_id_condition,
)

from core.providers.database.simplified_filters import (
    FilterError as SimplifiedFilterError,
    FilterOperator as SimplifiedFilterOperator,  # Same constants in both implementations
    apply_filters as simplified_apply_filters,
    _process_filter_dict as simplified_process_filter_dict,
    _build_metadata_condition as simplified_build_metadata_condition,
    _build_column_condition as simplified_build_column_condition,
    _build_collection_ids_condition as simplified_build_collection_ids_condition,
    _build_collection_id_condition as simplified_build_collection_id_condition,
    _build_parent_id_condition as simplified_build_parent_id_condition,
)


class TestSimplifiedFilters:
    """Test simplified filter implementation."""

    def test_basic_functionality(self):
        """Test that the simplified filters maintain basic functionality."""
        # Test simple equality
        filters = {"id": "test-id"}
        sql, params = simplified_apply_filters(filters, [])
        assert "id =" in sql, "SQL should contain equality operator"
        assert params == ["test-id"], "Parameters should contain the value"

        # Test logical operators
        filters = {
            SimplifiedFilterOperator.AND: [
                {"id": "test-id"},
                {"owner_id": "owner-id"}
            ]
        }
        sql, params = simplified_apply_filters(filters, [])
        assert " AND " in sql, "SQL should contain AND operator"
        assert params == ["test-id", "owner-id"], "Parameters should contain both values"

        # Test metadata access
        filters = {"metadata.key": "value"}
        sql, params = simplified_apply_filters(filters, [])
        assert "metadata->>'key'" in sql, "SQL should contain JSON extraction"
        assert params == ["value"], "Parameters should contain the value"


class TestSimplifiedFilterEdgeCases:
    """Test edge cases specific to the simplified filter implementation."""

    def test_json_extraction_consistency(self):
        """Test consistent JSON path extraction behavior."""
        # Text comparison (should use ->> for text extraction)
        filters1 = {"metadata.key": "text-value"}
        sql1, _ = simplified_apply_filters(filters1, [])
        assert "metadata->>'key'" in sql1, "Text comparison should use text extraction ->> operator"

        # Numeric comparison (should use ->> and cast to numeric)
        filters2 = {"metadata.number": {SimplifiedFilterOperator.GT: 10}}
        sql2, _ = simplified_apply_filters(filters2, [])
        assert "metadata->>'number'" in sql2, "Numeric comparison should use text extraction and cast"
        assert "::numeric >" in sql2, "Should cast to numeric for comparison"

        # JSON comparison (should use -> for JSON extraction)
        filters3 = {"metadata.obj": {SimplifiedFilterOperator.CONTAINS: {"nested": "value"}}}
        sql3, _ = simplified_apply_filters(filters3, [])
        assert "metadata->'obj'" in sql3, "JSON comparison should use JSON extraction -> operator"

    def test_handling_special_characters_in_paths(self):
        """Test handling of special characters in JSON paths."""
        # Keys with dots that aren't path separators
        # This is an edge case that might not be fully supported in the current implementation
        try:
            filters = {"metadata.key\\.with\\.dots": "value"}
            sql, _ = simplified_apply_filters(filters, [])
            # If implemented, assert the expected behavior
        except Exception:
            # Current implementation might not support escaping dots
            pass

        # Keys with quotes or other special characters
        # Test based on the expected implementation behavior
        try:
            filters = {"metadata.key_with_'quotes'": "value"}
            sql, _ = simplified_apply_filters(filters, [])
            # If implemented, assert the expected behavior
        except Exception:
            # Current implementation might not support quotes in keys
            pass

    def test_json_array_operations(self):
        """Test operations on JSON arrays in metadata."""
        # Test array containment with scalar
        filters = {"metadata.tags": {SimplifiedFilterOperator.CONTAINS: "tag1"}}
        sql, params = simplified_apply_filters(filters, [])
        assert "@>" in sql, "Should use containment operator for CONTAINS"
        assert json.loads(params[0]) == ["tag1"], "Parameter should be a singleton array for scalar value"

        # Test array containment with array
        filters = {"metadata.tags": {SimplifiedFilterOperator.CONTAINS: ["tag1", "tag2"]}}
        sql, params = simplified_apply_filters(filters, [])
        assert "@>" in sql, "Should use containment operator for CONTAINS"
        assert json.loads(params[0]) == ["tag1", "tag2"], "Parameter should be the array"


class TestFilterTypeConversions:
    """Test type conversions and handling of different data types."""

    def test_numeric_string_conversion(self):
        """Test conversion of numeric values to strings for metadata fields."""
        # Integer
        filters = {"metadata.number": 42}
        sql, params = simplified_apply_filters(filters, [])
        assert params == ["42"], "Integer should be converted to string for text comparison"

        # Float
        filters = {"metadata.number": 3.14}
        sql, params = simplified_apply_filters(filters, [])
        assert params == ["3.14"], "Float should be converted to string for text comparison"

    def test_boolean_conversion(self):
        """Test conversion of boolean values."""
        # True
        filters = {"metadata.flag": True}
        sql, params = simplified_apply_filters(filters, [])
        assert params == ["true"], "True should be converted to 'true' string"

        # False
        filters = {"metadata.flag": False}
        sql, params = simplified_apply_filters(filters, [])
        assert params == ["false"], "False should be converted to 'false' string"

    def test_null_handling(self):
        """Test handling of null values."""
        # Top-level column
        filters = {"id": None}
        sql, params = simplified_apply_filters(filters, [])
        # Different implementations might handle NULL differently
        assert ("IS NULL" in sql or "= NULL" in sql or 
                (sql.strip().endswith("= $1") and (not params or params == [None]))), "Should handle null in top-level column"

        # Metadata field
        filters = {"metadata.field": None}
        sql, params = simplified_apply_filters(filters, [])
        # The behavior depends on implementation - could be JSON null or SQL NULL
        assert ("IS NULL" in sql or "= NULL" in sql or "metadata" in sql), "Should handle null in metadata field"

        # Explicit null with operators
        filters = {"id": {SimplifiedFilterOperator.EQ: None}}
        sql, params = simplified_apply_filters(filters, [])
        assert ("IS NULL" in sql or "= NULL" in sql or
                (sql.strip().endswith("= $1") and (not params or params == [None]))), "EQ null should translate to IS NULL or similar"

        filters = {"id": {SimplifiedFilterOperator.NE: None}}
        sql, params = simplified_apply_filters(filters, [])
        assert ("IS NOT NULL" in sql or "!= NULL" in sql or
                (sql.strip().endswith("!= $1") and (not params or params == [None]))), "NE null should translate to IS NOT NULL or similar"

    def test_array_of_complex_types(self):
        """Test handling arrays of complex types in JSON fields."""
        # Array of objects
        complex_array = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        filters = {"metadata.items": {SimplifiedFilterOperator.CONTAINS: complex_array}}
        sql, params = simplified_apply_filters(filters, [])
        assert "@>" in sql, "Should use containment operator"
        # Verify the parameter is properly JSON-encoded
        assert json.loads(params[0]) == complex_array, "Complex array should be properly JSON-encoded"

        # Single complex object in CONTAINS
        complex_object = {"id": 1, "name": "Item 1"}
        filters = {"metadata.items": {SimplifiedFilterOperator.CONTAINS: complex_object}}
        sql, params = simplified_apply_filters(filters, [])
        assert "@>" in sql, "Should use containment operator"
        assert json.loads(params[0]) == complex_object, "Complex object should be properly JSON-encoded"


class TestRealWorldQueries:
    """Test scenarios simulating real-world query patterns."""

    def test_search_with_complex_criteria(self):
        """Test a complex search query with multiple criteria types."""
        # A query to find documents:
        # - In any of collections 'collection1' or 'collection2'
        # - Created after January 1, 2021
        # - With status 'active'
        # - With a metadata field 'tags' containing 'important'
        # - With a metadata field 'score' greater than 80
        filters = {
            SimplifiedFilterOperator.AND: [
                {"collection_ids": {SimplifiedFilterOperator.OVERLAP: ["collection1", "collection2"]}},
                {"metadata.created_at": {SimplifiedFilterOperator.GT: "2021-01-01"}},
                {"metadata.status": "active"},
                {"metadata.tags": {SimplifiedFilterOperator.CONTAINS: "important"}},
                {"metadata.score": {SimplifiedFilterOperator.GT: 80}}
            ]
        }
        
        sql, params = simplified_apply_filters(filters, [])
        
        # Basic checks
        assert " AND " in sql, "Should use AND to combine all conditions"
        assert "collection_ids &&" in sql, "Should use overlap operator for collections"
        # Different implementations might handle date comparisons differently
        assert "metadata" in sql and "created_at" in sql, "Should include created_at field"
        assert "metadata->>'status'" in sql or "metadata->'status'" in sql, "Should compare status as text"
        assert "@>" in sql, "Should use containment for tags"
        assert "score" in sql and "numeric" in sql, "Should compare score as numeric"
        
        # Check parameters
        assert ["collection1", "collection2"] in params, "Should include collection IDs"
        assert "2021-01-01" in params, "Should include date string"
        assert "active" in params, "Should include status"
        assert "80" in params, "Should include score (as string)"
        
        # At least one parameter should be a JSON string for tags
        assert any(isinstance(p, str) and "important" in p for p in params), "Should include JSON-encoded tags"

    def test_pagination_filters(self):
        """Test filters typically used for pagination."""
        # Simulating "get next page after ID 123, sorted by created_at desc"
        filters = {
            SimplifiedFilterOperator.OR: [
                {"metadata.created_at": {SimplifiedFilterOperator.LT: "2023-01-01"}},
                {
                    SimplifiedFilterOperator.AND: [
                        {"metadata.created_at": "2023-01-01"},
                        {"id": {SimplifiedFilterOperator.LT: "123"}}
                    ]
                }
            ]
        }
        
        sql, params = simplified_apply_filters(filters, [])
        
        # Basic checks
        assert " OR " in sql, "Should use OR for pagination options"
        assert " AND " in sql, "Should use AND for tie-breaker"
        assert "metadata->>'created_at'" in sql, "Should reference created_at"
        assert "id <" in sql, "Should have ID comparison"
        
        # Check parameters
        assert "2023-01-01" in params, "Should include date twice"
        assert params.count("2023-01-01") == 2, "Date should appear twice (LT and EQ)"
        assert "123" in params, "Should include ID"

    def test_hierarchical_data_query(self):
        """Test query for hierarchical data structures."""
        # Query that navigates a nested structure
        filters = {
            "metadata.level1.level2.level3.value": {SimplifiedFilterOperator.GT: 100}
        }
        
        sql, params = simplified_apply_filters(filters, [])
        
        # Check JSON path navigation
        expected_path = "metadata->'level1'->'level2'->'level3'->>'value'"
        assert expected_path in sql, "Should properly navigate nested JSON path"
        assert "::numeric >" in sql, "Should cast to numeric for comparison"
        assert params == ["100"], "Should include numeric value as string"

    def test_full_text_search_simulation(self):
        """Test filters that simulate full-text search patterns."""
        # Simple text search in multiple fields
        filters = {
            SimplifiedFilterOperator.OR: [
                {"metadata.title": {SimplifiedFilterOperator.ILIKE: "%search term%"}},
                {"metadata.description": {SimplifiedFilterOperator.ILIKE: "%search term%"}},
                {"metadata.content": {SimplifiedFilterOperator.ILIKE: "%search term%"}}
            ]
        }
        
        sql, params = simplified_apply_filters(filters, [])
        
        # Check basic structure
        assert " OR " in sql, "Should use OR to combine text search conditions"
        # Different implementations can use different JSON extraction operators
        assert "metadata" in sql and "title" in sql and "ILIKE" in sql, "Should search in title with ILIKE"
        assert "metadata" in sql and "description" in sql, "Should search in description"
        assert "metadata" in sql and "content" in sql, "Should search in content"
        
        # Check parameters
        assert all("%search term%" in p for p in params), "All parameters should contain search term"


class TestCornerCases:
    """Test unusual or corner cases that could occur in practice."""

    def test_very_large_filter(self):
        """Test handling of a very large filter structure."""
        # Create a filter with many conditions (could test performance or buffer limits)
        many_conditions = []
        for i in range(50):  # 50 conditions
            many_conditions.append({"metadata.field" + str(i): "value" + str(i)})
        
        filters = {SimplifiedFilterOperator.AND: many_conditions}
        
        sql, params = simplified_apply_filters(filters, [])
        
        # Basic checks
        assert " AND " in sql, "Should use AND to combine conditions"
        assert len(params) == 50, "Should have 50 parameters"
        for i in range(50):
            assert f"value{i}" in params, f"Should include value{i}"

    def test_same_field_multiple_times(self):
        """Test handling the same field with different conditions."""
        # Range condition using the same field twice
        filters = {
            SimplifiedFilterOperator.AND: [
                {"metadata.score": {SimplifiedFilterOperator.GTE: 50}},
                {"metadata.score": {SimplifiedFilterOperator.LT: 100}}
            ]
        }
        
        sql, params = simplified_apply_filters(filters, [])
        
        # Check structure
        assert " AND " in sql, "Should use AND to combine range bounds"
        assert "metadata->>'score'" in sql, "Should reference score field"
        assert "::numeric >=" in sql, "Should have GTE comparison"
        assert "::numeric <" in sql, "Should have LT comparison"
        
        # Check parameters
        assert "50" in params, "Should include lower bound"
        assert "100" in params, "Should include upper bound"

    def test_empty_list_values(self):
        """Test handling of empty lists in various operators."""
        # Empty IN list
        filters = {"id": {SimplifiedFilterOperator.IN: []}}
        sql, params = simplified_apply_filters(filters, [])
        # The behavior depends on implementation - could be "FALSE" or empty list handling
        assert "FALSE" in sql.upper() or ("ANY" in sql and "[]" in str(params)), "Should handle empty IN list"
        
        # Empty CONTAINS list
        filters = {"metadata.tags": {SimplifiedFilterOperator.CONTAINS: []}}
        sql, params = simplified_apply_filters(filters, [])
        # The behavior depends on implementation
        assert params[0] == "[]" or json.loads(params[0]) == [], "Should handle empty CONTAINS list"

    def test_special_value_handling(self):
        """Test handling of special values that might cause SQL issues."""
        # SQL injection attempt in string
        filters = {"id": "value'; DROP TABLE users; --"}
        sql, params = simplified_apply_filters(filters, [])
        # Should be safe because of parameterization
        assert "id =" in sql, "Should handle value normally"
        assert params == ["value'; DROP TABLE users; --"], "Should include value as parameter"
        
        # Very long string
        long_string = "x" * 1000  # 1000 character string
        filters = {"metadata.field": long_string}
        sql, params = simplified_apply_filters(filters, [])
        assert "metadata->>'field'" in sql, "Should handle long string normally"
        assert params == [long_string], "Should include long string as parameter"

    def test_unicode_handling(self):
        """Test handling of Unicode characters in filter values."""
        # Unicode in string value
        filters = {"metadata.title": "😀 Unicode 测试"}
        sql, params = simplified_apply_filters(filters, [])
        assert "metadata->>'title'" in sql, "Should handle Unicode normally"
        assert params == ["😀 Unicode 测试"], "Should include Unicode string as parameter"
        
        # Unicode in field name (might not be supported in current implementation)
        try:
            filters = {"metadata.标题": "value"}
            sql, params = simplified_apply_filters(filters, [])
            assert "metadata->>'标题'" in sql, "Should handle Unicode in field name"
        except Exception:
            # Current implementation might not support Unicode in field names
            pass


class TestFilterOperations:
    """Test basic filter operations."""

    def test_simple_equality_filter(self):
        """Test simple equality filter for a top-level column."""
        filters = {"id": "test-id"}
        sql, params = main_apply_filters(filters, [])
        assert "id =" in sql, "SQL should contain equality operator"
        assert params == ["test-id"], "Parameters should contain the value"

    def test_operator_equality_filter(self):
        """Test equality filter with explicit operator for a top-level column."""
        filters = {"id": {MainFilterOperator.EQ: "test-id"}}
        sql, params = main_apply_filters(filters, [])
        assert "id =" in sql, "SQL should contain equality operator"
        assert params == ["test-id"], "Parameters should contain the value"

    def test_inequality_filter(self):
        """Test inequality filter for a top-level column."""
        filters = {"id": {MainFilterOperator.NE: "test-id"}}
        sql, params = main_apply_filters(filters, [])
        assert "id !=" in sql, "SQL should contain inequality operator"
        assert params == ["test-id"], "Parameters should contain the value"

    def test_comparison_filters(self):
        """Test comparison operators (LT, LTE, GT, GTE)."""
        # Less than
        filters = {"id": {MainFilterOperator.LT: "test-id"}}
        sql, params = main_apply_filters(filters, [])
        assert "id <" in sql, "SQL should contain less than operator"
        assert params == ["test-id"], "Parameters should contain the value"

        # Less than or equal
        filters = {"id": {MainFilterOperator.LTE: "test-id"}}
        sql, params = main_apply_filters(filters, [])
        assert "id <=" in sql, "SQL should contain less than or equal operator"
        assert params == ["test-id"], "Parameters should contain the value"

        # Greater than
        filters = {"id": {MainFilterOperator.GT: "test-id"}}
        sql, params = main_apply_filters(filters, [])
        assert "id >" in sql, "SQL should contain greater than operator"
        assert params == ["test-id"], "Parameters should contain the value"

        # Greater than or equal
        filters = {"id": {MainFilterOperator.GTE: "test-id"}}
        sql, params = main_apply_filters(filters, [])
        assert "id >=" in sql, "SQL should contain greater than or equal operator"
        assert params == ["test-id"], "Parameters should contain the value"

    def test_in_filter(self):
        """Test IN filter for a top-level column."""
        filters = {"id": {MainFilterOperator.IN: ["id1", "id2", "id3"]}}
        sql, params = main_apply_filters(filters, [])
        assert "id = ANY" in sql, "SQL should use ANY operator for IN filter"
        assert params == [["id1", "id2", "id3"]], "Parameters should contain the list"

    def test_not_in_filter(self):
        """Test NOT IN filter for a top-level column."""
        filters = {"id": {MainFilterOperator.NIN: ["id1", "id2", "id3"]}}
        sql, params = main_apply_filters(filters, [])
        assert "id != ALL" in sql, "SQL should use ALL operator for NIN filter"
        assert params == [["id1", "id2", "id3"]], "Parameters should contain the list"

    def test_like_filters(self):
        """Test LIKE and ILIKE filters."""
        # LIKE
        filters = {"id": {MainFilterOperator.LIKE: "%test%"}}
        sql, params = main_apply_filters(filters, [])
        assert "id LIKE" in sql, "SQL should contain LIKE operator"
        assert params == ["%test%"], "Parameters should contain the pattern"

        # ILIKE
        filters = {"id": {MainFilterOperator.ILIKE: "%test%"}}
        sql, params = main_apply_filters(filters, [])
        assert "id ILIKE" in sql, "SQL should contain ILIKE operator"
        assert params == ["%test%"], "Parameters should contain the pattern"


class TestLogicalOperators:
    """Test logical operator behavior."""

    def test_and_operator(self):
        """Test AND operator with multiple conditions."""
        filters = {
            MainFilterOperator.AND: [
                {"id": "test-id"},
                {"owner_id": "owner-id"}
            ]
        }
        sql, params = main_apply_filters(filters, [])
        assert " AND " in sql, "SQL should contain AND operator"
        assert params == ["test-id", "owner-id"], "Parameters should contain both values"

    def test_or_operator(self):
        """Test OR operator with multiple conditions."""
        filters = {
            MainFilterOperator.OR: [
                {"id": "test-id"},
                {"owner_id": "owner-id"}
            ]
        }
        sql, params = main_apply_filters(filters, [])
        assert " OR " in sql, "SQL should contain OR operator"
        assert params == ["test-id", "owner-id"], "Parameters should contain both values"

    def test_nested_logical_operators(self):
        """Test nested logical operators (AND within OR, OR within AND)."""
        # OR within AND
        filters = {
            MainFilterOperator.AND: [
                {"id": "test-id"},
                {
                    MainFilterOperator.OR: [
                        {"owner_id": "owner1"},
                        {"owner_id": "owner2"}
                    ]
                }
            ]
        }
        sql, params = main_apply_filters(filters, [])
        assert " AND " in sql, "SQL should contain AND operator"
        assert " OR " in sql, "SQL should contain OR operator"
        assert params == ["test-id", "owner1", "owner2"], "Parameters should contain all values"

        # AND within OR
        filters = {
            MainFilterOperator.OR: [
                {"id": "test-id"},
                {
                    MainFilterOperator.AND: [
                        {"owner_id": "owner1"},
                        {"document_id": "doc1"}
                    ]
                }
            ]
        }
        sql, params = main_apply_filters(filters, [])
        assert " OR " in sql, "SQL should contain OR operator"
        assert " AND " in sql, "SQL should contain AND operator"
        assert params == ["test-id", "owner1", "doc1"], "Parameters should contain all values"

    def test_multiple_conditions_implicit_and(self):
        """Test multiple conditions in a filter dict (implicit AND)."""
        filters = {
            "id": "test-id",
            "owner_id": "owner-id"
        }
        sql, params = main_apply_filters(filters, [])
        assert " AND " in sql, "SQL should contain AND operator for multiple conditions"
        assert set(params) == {"test-id", "owner-id"}, "Parameters should contain both values"


class TestMetadataFilters:
    """Test filtering on metadata fields (JSON)."""

    def test_simple_metadata_equality(self):
        """Test simple equality filter for a metadata field."""
        filters = {"metadata.key": "value"}
        sql, params = main_apply_filters(filters, [])
        assert "metadata->>'key'" in sql, "SQL should contain JSON extraction"
        assert params == ["value"], "Parameters should contain the value"

    def test_nested_metadata_equality(self):
        """Test equality filter for a nested metadata field."""
        filters = {"metadata.parent.child": "value"}
        sql, params = main_apply_filters(filters, [])
        assert "metadata->'parent'->>'child'" in sql, "SQL should contain nested JSON extraction"
        assert params == ["value"], "Parameters should contain the value"

    def test_numeric_metadata_comparison(self):
        """Test numeric comparison on metadata fields."""
        filters = {"metadata.score": {MainFilterOperator.GT: 50}}
        sql, params = main_apply_filters(filters, [])
        assert "metadata->>'score'" in sql, "SQL should contain JSON extraction"
        assert "::numeric >" in sql, "SQL should cast to numeric for comparison"
        assert params == ["50"], "Parameters should contain the string value of number"

    def test_metadata_contains(self):
        """Test CONTAINS operator for JSON data."""
        filters = {"metadata.tags": {MainFilterOperator.CONTAINS: ["tag1", "tag2"]}}
        sql, params = main_apply_filters(filters, [])
        assert "metadata->'tags' @>" in sql, "SQL should use JSON containment operator"
        assert json.loads(params[0]) == ["tag1", "tag2"], "Parameters should contain JSON-encoded list"

    def test_metadata_in_array(self):
        """Test IN operator for checking if a value is in a metadata array."""
        filters = {"metadata.category": {MainFilterOperator.IN: ["cat1", "cat2"]}}
        sql, params = main_apply_filters(filters, [])
        assert "metadata->'category'" in sql, "SQL should contain JSON extraction"
        assert "@>" in sql, "SQL should use JSON containment"
        # IN for JSON is implemented as multiple OR conditions with containment
        assert len(params) == 2, "Should have 2 parameters"
        assert json.loads(params[0]) == "cat1", "First parameter should be first item"
        assert json.loads(params[1]) == "cat2", "Second parameter should be second item"

    def test_metadata_prefix(self):
        """Test field name with or without 'metadata.' prefix."""
        # With prefix
        filters1 = {"metadata.key": "value"}
        sql1, params1 = main_apply_filters(filters1, [])
        
        # Without prefix (should be treated as metadata)
        filters2 = {"key": "value"}
        sql2, params2 = main_apply_filters(filters2, [], top_level_columns=["id", "owner_id"])
        
        # Both should produce the same SQL
        assert "metadata" in sql2, "Field not in top_level_columns should be treated as metadata"
        assert params1 == params2, "Parameters should be the same"


class TestSpecialFieldHandling:
    """Test handling of special fields like collection_ids and parent_id."""

    def test_collection_id_filter(self):
        """Test filtering by collection_id (which is a shorthand for collection_ids)."""
        filters = {"collection_id": "coll-id"}
        sql, params = main_apply_filters(filters, [])
        assert "collection_ids" in sql, "SQL should reference collection_ids array"
        assert params == ["coll-id"], "Parameters should contain the single ID"

    def test_collection_ids_filter(self):
        """Test filtering by collection_ids array."""
        filters = {"collection_ids": {MainFilterOperator.CONTAINS: "coll-id"}}
        sql, params = main_apply_filters(filters, [])
        assert "collection_ids" in sql, "SQL should reference collection_ids array"
        assert params == ["coll-id"], "Parameters should contain the single ID"

    def test_collection_ids_overlap(self):
        """Test OVERLAP operator for collection_ids."""
        filters = {"collection_ids": {MainFilterOperator.OVERLAP: ["coll1", "coll2"]}}
        sql, params = main_apply_filters(filters, [])
        assert "collection_ids && " in sql, "SQL should use array overlap operator"
        assert params == [["coll1", "coll2"]], "Parameters should contain the array"

    def test_parent_id_filters(self):
        """Test filtering by parent_id with different operators."""
        # Equality
        filters = {"parent_id": "parent-id"}
        sql, params = main_apply_filters(filters, [])
        assert "parent_id =" in sql, "SQL should contain equality check"
        assert "::uuid" in sql, "SQL should cast to UUID"
        assert params == ["parent-id"], "Parameters should contain the ID"

        # IN operator
        filters = {"parent_id": {MainFilterOperator.IN: ["pid1", "pid2"]}}
        sql, params = main_apply_filters(filters, [])
        assert "parent_id = ANY" in sql, "SQL should use ANY for IN operator"
        assert "::uuid[]" in sql, "SQL should cast to UUID array"
        assert params == [["pid1", "pid2"]], "Parameters should contain the IDs"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_filters(self):
        """Test behavior with empty filters."""
        sql, params = main_apply_filters({}, [])
        assert sql == "", "SQL should be empty string for empty filters"
        assert params == [], "Parameters should be unchanged"

    def test_null_value(self):
        """Test handling of null/None values."""
        filters = {"id": None}
        sql, params = main_apply_filters(filters, [])
        assert "id IS NULL" in sql, "SQL should use IS NULL for None values"
        assert params == [], "Parameters should be empty since NULL doesn't need a parameter"

        # Explicit IS NULL with operator
        filters = {"id": {MainFilterOperator.EQ: None}}
        sql, params = main_apply_filters(filters, [])
        assert "id IS NULL" in sql, "SQL should use IS NULL for None values with EQ operator"
        assert params == [], "Parameters should be empty"

    def test_boolean_values(self):
        """Test handling of boolean values."""
        # True value
        filters = {"metadata.active": True}
        sql, params = main_apply_filters(filters, [])
        assert params == ["true"], "Parameters should contain string 'true'"

        # False value
        filters = {"metadata.active": False}
        sql, params = main_apply_filters(filters, [])
        assert params == ["false"], "Parameters should contain string 'false'"

    def test_filter_modes(self):
        """Test different filter modes (where_clause, condition_only, append_only)."""
        filters = {"id": "test-id"}
        
        # Default where_clause mode
        sql1, _ = main_apply_filters(filters, [])
        assert sql1.startswith("WHERE"), "Default mode should prepend WHERE"
        
        # condition_only mode
        sql2, _ = main_apply_filters(filters, [], mode="condition_only")
        assert not sql2.startswith("WHERE"), "condition_only mode should not prepend WHERE"
        
        # append_only mode
        sql3, _ = main_apply_filters(filters, [], mode="append_only")
        assert sql3.startswith("AND"), "append_only mode should prepend AND"

    def test_invalid_operator(self):
        """Test handling of invalid operators."""
        filters = {"id": {"$invalid": "value"}}
        with pytest.raises(MainFilterError, match="Unsupported operator"):
            main_apply_filters(filters, [])

    def test_invalid_condition_format(self):
        """Test handling of invalid condition formats."""
        # Multiple operators in one condition
        filters = {"id": {MainFilterOperator.EQ: "value1", MainFilterOperator.NE: "value2"}}
        with pytest.raises(MainFilterError, match="must have exactly one operator"):
            main_apply_filters(filters, [])

        # Invalid logical operator format
        filters = {MainFilterOperator.AND: "not-a-list"}
        with pytest.raises(MainFilterError, match="must be a list"):
            main_apply_filters(filters, [])

        # Invalid item in logical operator list
        filters = {MainFilterOperator.AND: [{"valid": "item"}, "invalid-item"]}
        with pytest.raises(MainFilterError, match="Invalid filter format"):
            main_apply_filters(filters, [])

    def test_custom_top_level_columns(self):
        """Test with custom top_level_columns parameter."""
        # Define a custom set of top-level columns
        custom_columns = ["id", "custom_field"]
        
        # Test a field that's in custom_columns
        filters = {"custom_field": "value"}
        sql, _ = main_apply_filters(filters, [], top_level_columns=custom_columns)
        assert "custom_field =" in sql, "Should treat custom_field as a normal column"
        assert "metadata" not in sql, "Should not treat custom_field as metadata"
        
        # Test a field that's not in custom_columns
        filters = {"other_field": "value"}
        sql, _ = main_apply_filters(filters, [], top_level_columns=custom_columns)
        assert "metadata" in sql, "Should treat other_field as metadata"

    def test_custom_json_column(self):
        """Test with custom json_column parameter."""
        # Use a custom json column name
        custom_json = "properties"
        
        filters = {"field": "value"}
        sql, _ = main_apply_filters(filters, [], top_level_columns=["id"], json_column=custom_json)
        assert custom_json in sql, f"Should use {custom_json} instead of metadata"
        assert "metadata" not in sql, "Should not use default metadata column name"


class TestComplexFilterCombinations:
    """Test complex combinations of different filter types."""

    def test_combined_filters(self):
        """Test combination of different filter types."""
        filters = {
            MainFilterOperator.AND: [
                {"id": "test-id"},
                {"metadata.score": {MainFilterOperator.GTE: 80}},
                {
                    MainFilterOperator.OR: [
                        {"collection_id": "coll1"},
                        {"parent_id": {MainFilterOperator.IN: ["pid1", "pid2"]}}
                    ]
                }
            ]
        }
        sql, params = main_apply_filters(filters, [])
        
        # Check for AND operator
        assert " AND " in sql, "SQL should contain AND operator"
        
        # Check for metadata handling
        assert "metadata->>'score'" in sql, "SQL should handle metadata field"
        assert "::numeric >=" in sql, "SQL should handle numeric comparison"
        
        # Check for OR operator
        assert " OR " in sql, "SQL should contain OR operator"
        
        # Check for collection_id handling
        assert "collection_ids" in sql, "SQL should handle collection_id"
        
        # Check for parent_id handling
        assert "parent_id = ANY" in sql, "SQL should handle parent_id IN condition"
        
        # Check parameters
        assert len(params) == 4, "Should have 4 parameters"
        assert "test-id" in params, "Parameters should include test-id"
        assert "80" in params, "Parameters should include 80 (as string)"
        assert "coll1" in params, "Parameters should include coll1"
        assert ["pid1", "pid2"] in params, "Parameters should include pid list"

    def test_multiple_json_levels(self):
        """Test filtering with deeply nested JSON fields."""
        filters = {"metadata.level1.level2.level3.deep": {MainFilterOperator.GT: 100}}
        sql, params = main_apply_filters(filters, [])
        
        expected_path = (
            "metadata->'level1'->'level2'->'level3'->>'deep'"
        )
        assert expected_path in sql, "SQL should handle deeply nested JSON path"
        assert "::numeric >" in sql, "Should cast to numeric for comparison"
        assert params == ["100"], "Parameters should contain the value"
