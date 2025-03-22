"""
Database utility functions for PostgreSQL operations.
"""


def psql_quote_literal(value: str) -> str:
    """Safely quote a string literal for PostgreSQL to prevent SQL injection.

    This is a simple implementation - in production, you should use proper parameterization
    or your database driver's quoting functions.
    """
    return "'" + value.replace("'", "''") + "'"
