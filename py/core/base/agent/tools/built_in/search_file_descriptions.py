from core.base.agent.tools.base import Tool
from typing import Callable
import logging

logger = logging.getLogger(__name__)

class SearchFileDescriptionTool:
    """
    A tool to search over high-level document data (titles, descriptions, etc.)
    """
    
    def __init__(self):
        self.name = "search_file_descriptions"
        self.description = (
            "Semantic search over the stored documents over AI generated summaries of input documents. "
            "This does NOT retrieve chunk-level contents or knowledge-graph relationships. "
            "Use this when you need a broad overview of which documents (files) might be relevant."
        )
        self.parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query string to semantic search over available files 'list documents about XYZ'.",
                }
            },
            "required": ["query"],
        },
    
    async def execute(self, query: str, context=None, *args, **kwargs):
        """
        Calls the file_search_method from context.
        """
        from core.base.abstractions import AggregateSearchResult
        
        # Check if context has necessary method
        if not context or not hasattr(context, 'file_search_method'):
            logger.error("No file_search_method provided in context")
            return AggregateSearchResult(document_search_results=[])
        
        # Get the content_method from context
        file_search_method = context.file_search_method

        # Call the content_method from the context
        try:
            """
            FIXME: This is going to fail, as it requires an embedding NOT a query.
            I've moved 'search_settings' to 'settings' which had been causing a silent failure
            causing null content in the Message object.
            """
            doc_results = await file_search_method(
                query=query,
                settings=context.search_settings,
            )
        except Exception as e:
            logger.error(f"Error calling content_method: {e}")
            return AggregateSearchResult(document_search_results=[])

        # Return them in the new aggregator field
        result = AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=None,
            document_search_results=doc_results,
        )

        # Add to results collector if context has it
        if hasattr(context, 'search_results_collector'):
            context.search_results_collector.add_aggregate_result(result)
            
        return result
    
    def create_tool(self, format_function: Callable) -> Tool:
        """
        Create and configure a Tool instance with the provided format function.
        """
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            results_function=self.execute,
            llm_format_function=format_function,
        )
