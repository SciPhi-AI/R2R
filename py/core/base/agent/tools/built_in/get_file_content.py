from core.base.agent.tools.base import Tool
from typing import Callable, Optional, Any
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

class FileContentTool:
    """
    A tool to fetch entire documents from the local database.

    Typically used if the agent needs deeper or more structured context
    from documents, not just chunk-level hits.
    """
    
    def __init__(self):
        self.name = "get_file_content"
        self.description = (
            "Fetches the complete contents of all user documents from the local database. "
            "Can be used alongside filter criteria (e.g. doc IDs, collection IDs, etc.) to restrict the query."
            "For instance, a single document can be returned with a filter like so:"
            "{'document_id': {'$eq': '...'}}."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The unique UUID of the document to fetch.",
                },
            },
            "required": ["document_id"],
        }
    
    async def execute(self, document_id: str, context=None, options: Optional[dict[str, Any]] = None, *args, **kwargs):
        """
        Calls the content_method from context to fetch doc+chunk structures.
        """
        from core.base.abstractions import AggregateSearchResult
        
        # Check if context has necessary method
        if not context or not hasattr(context, 'content_method'):
            logger.error("No content_method provided in context")
            return AggregateSearchResult(document_search_results=[])
        
        # Get the content_method from context
        content_method = context.content_method
        
        try:
            doc_uuid = UUID(document_id)
            filters = {"id": {"$eq": doc_uuid}}
        except ValueError:
            # Handle invalid UUID format passed by LLM
            logger.error(f"Invalid document_id format received: {document_id}")
            # Return empty result or raise specific error
            return AggregateSearchResult(document_search_results=[])

        options = options or {}

        # Call the content_method from the context
        try:
            content = await content_method(filters, options)
        except Exception as e:
            logger.error(f"Error calling content_method: {e}")
            return AggregateSearchResult(document_search_results=[])

        # Return them in the new aggregator field
        result = AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=None,
            document_search_results=content,
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
