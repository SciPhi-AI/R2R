import logging
from typing import Any, Optional
from uuid import UUID

from core.base.agent.tools.base import Tool

logger = logging.getLogger(__name__)


class GetFileContentTool(Tool):
    """
    A tool to fetch entire documents from the local database.

    Typically used if the agent needs deeper or more structured context
    from documents, not just chunk-level hits.
    """

    def __init__(self):
        # Initialize with all required fields for the Pydantic model
        super().__init__(
            name="get_file_content",
            description=(
                "Fetches the complete contents of all user documents from the local database. "
                "Can be used alongside filter criteria (e.g. doc IDs, collection IDs, etc.) to restrict the query."
                "For instance, a single document can be returned with a filter like so:"
                "{'document_id': {'$eq': '...'}}."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The unique UUID of the document to fetch.",
                    },
                },
                "required": ["document_id"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(
        self,
        document_id: str,
        options: Optional[dict[str, Any]] = None,
        *args,
        **kwargs,
    ):
        """
        Calls the content_method from context to fetch doc+chunk structures.
        """
        from core.base.abstractions import AggregateSearchResult

        # Use either provided context or stored context
        context = self.context

        # Check if context has necessary method
        if not context or not hasattr(context, "content_method"):
            logger.error("No content_method provided in context")
            return AggregateSearchResult(document_search_results=[])

        try:
            doc_uuid = UUID(document_id)
            filters = {"id": {"$eq": doc_uuid}}
        except ValueError:
            logger.error(f"Invalid document_id format received: {document_id}")
            return AggregateSearchResult(document_search_results=[])

        options = options or {}

        try:
            content = await context.content_method(filters, options)
        except Exception as e:
            logger.error(f"Error calling content_method: {e}")
            return AggregateSearchResult(document_search_results=[])

        result = AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=None,
            document_search_results=content,
        )

        if hasattr(context, "search_results_collector"):
            context.search_results_collector.add_aggregate_result(result)

        return result
