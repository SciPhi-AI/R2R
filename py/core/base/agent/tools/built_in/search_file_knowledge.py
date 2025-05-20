import logging

from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class SearchFileKnowledgeTool(Tool):
    """
    A tool to do a semantic/hybrid search on the local knowledge base.
    """

    def __init__(self):
        super().__init__(
            name="search_file_knowledge",
            description=(
                "Search your local knowledge base using the R2R system. "
                "Use this when you want relevant text chunks or knowledge graph data."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User query to search in the local DB.",
                    },
                },
                "required": ["query"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(self, query: str, *args, **kwargs):
        """
        Calls the knowledge_search_method from context.
        """
        from core.base.abstractions import AggregateSearchResult

        context = self.context

        # Check if context has necessary method
        if not context or not hasattr(context, "knowledge_search_method"):
            logger.error("No knowledge_search_method provided in context")
            return AggregateSearchResult(document_search_results=[])

        # Get the knowledge_search_method from context
        knowledge_search_method = context.knowledge_search_method

        # Call the content_method from the context
        try:
            """
            FIXME: This is going to fail, as it requires an embedding NOT a query.
            I've moved 'search_settings' to 'settings' which had been causing a silent failure
            causing null content in the Message object.
            """
            results = await knowledge_search_method(
                query=query,
                search_settings=context.search_settings,
            )

            # FIXME: This is slop
            if isinstance(results, AggregateSearchResult):
                agg = results
            else:
                agg = AggregateSearchResult(
                    chunk_search_results=results.get(
                        "chunk_search_results", []
                    ),
                    graph_search_results=results.get(
                        "graph_search_results", []
                    ),
                )
        except Exception as e:
            logger.error(f"Error calling content_method: {e}")
            return AggregateSearchResult(document_search_results=[])

        # Add to results collector if context has it
        if hasattr(context, "search_results_collector"):
            context.search_results_collector.add_aggregate_result(agg)

        return agg
