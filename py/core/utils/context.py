from contextvars import ContextVar, Token

project_schema_context: ContextVar[str | None] = ContextVar(
    "project_schema_context", default=None
)


def get_current_project_schema() -> str | None:
    """Get the current project schema name from context."""
    return project_schema_context.get()


def set_project_schema(schema_name: str) -> Token:
    """Set the current project schema in context."""
    return project_schema_context.set(schema_name)
