import logging

from smolagents import Tool as SmolTool

from core.base.agent.tools.built_in.smart_filter import SmartFilterTool
from shared.abstractions.tool import Tool as R2RTool

logger = logging.getLogger(__name__)


class SmolSmartFilterTool(SmolTool):
    name = "smol_smart_filter"
    description = "Refines metadata and collection filters for a RAG search using LLM analysis. To be used BEFORE the rag search"
    inputs = {
        "query": {
            "type": "string",
            "description": "The user query to analyze.",
        }
    }
    output_type = "object"
    parameters = inputs

    def __init__(self, context, r2r_tool: R2RTool, **kwargs):
        super().__init__()
        self.context = context
        self.results_function = self.forward
        self._r2r_tool = r2r_tool

    async def forward(self, query: str):
        return await self._r2r_tool.execute(query)


class SmolSmartFilterToolR2RWrapper(R2RTool):
    def __init__(self):
        super().__init__(
            name="smol_smart_filter_tool",
            description="Wrapper for the SmolSmartFilterTool to be used in R2R",
            results_function=self.execute,
        )
        self._r2r_tool = SmartFilterTool()
        self._smol_tool = SmolSmartFilterTool(
            context=self, r2r_tool=self._r2r_tool
        )

    async def execute(self, query: str, **kwargs):
        logger.debug(
            f"Executing SmolSmartFilterToolR2RWrapper with query: {query}"
        )
        return await self._r2r_tool.execute(query)
