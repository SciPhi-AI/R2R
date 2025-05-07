import logging

from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class SearchFileDescriptionsTool(Tool):
    """
    A tool to search over high-level document data (titles, descriptions, etc.)
    """

    def __init__(self):
        super().__init__(
            name="search_file_descriptions",
            description=(
                "Semantic search over AI-generated summaries of stored documents. "
                "This does NOT retrieve chunk-level contents or knowledge-graph relationships. "
                "Use this when you need a broad overview of which documents (files) might be relevant."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query string to semantic search over available files 'list documents about XYZ'.",
                    }
                },
                "required": ["query"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(self, query: str, *args, **kwargs):
        """
        Calls the file_search_method from context.
        """
        from core.base.abstractions import AggregateSearchResult

        context = self.context

        # Check if context has necessary method
        if not context or not hasattr(context, "file_search_method"):
            logger.error("No file_search_method provided in context")
            return AggregateSearchResult(document_search_results=[])

        # Get the file_search_method from context
        file_search_method = context.file_search_method

        # Call the content_method from the context
        try:
            doc_results = await file_search_method(
                query=query,
                settings=context.search_settings,
            )
        except Exception as e:
            logger.error(f"Error calling content_method: {e}")
            return AggregateSearchResult(document_search_results=[])

        result = AggregateSearchResult(document_search_results=doc_results)

        # Add to results collector if context has it
        if hasattr(context, "search_results_collector"):
            context.search_results_collector.add_aggregate_result(result)

        return result
