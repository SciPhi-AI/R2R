import logging

from smolagents import Tool as SmolTool

from core.base.agent.tools.built_in.search_file_descriptions import (
    SearchFileDescriptionsTool,
)
from shared.abstractions.tool import Tool as R2RTool

logger = logging.getLogger(__name__)


class SmolSearchFileDescriptionsTool(SmolTool):
    name = "smol_search_file_descriptions"
    description = "Semantic search over AI-generated summaries of stored documents. Use for a broad overview of relevant files."
    inputs = {
        "query": {
            "type": "string",
            "description": "Query string to semantic search over available files.",
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


class SmolSearchFileDescriptionsToolR2RWrapper(R2RTool):
    def __init__(self):
        super().__init__(
            name="smol_search_file_descriptions",
            description="Wrapper for the SmolSearchFileDescriptionsTool to be used in R2R",
            results_function=self.execute,
        )
        self._r2r_tool = SearchFileDescriptionsTool()
        self._smol_tool = SmolSearchFileDescriptionsTool(
            context=self, r2r_tool=self._r2r_tool
        )

    async def execute(self, query: str, **kwargs):
        logger.debug(
            f"Executing SmolSearchFileDescriptionsToolR2RWrapper with query: {query}"
        )
        return await self._r2r_tool.execute(query)
