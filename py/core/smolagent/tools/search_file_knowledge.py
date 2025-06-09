import logging

from smolagents import Tool as SmolTool

from core.base.agent.tools.built_in.search_file_knowledge import (
    SearchFileKnowledgeTool,
)
from shared.abstractions.tool import Tool as R2RTool

logger = logging.getLogger(__name__)


class SmolSearchFileKnowledgeTool(SmolTool):
    name = "smol_search_file_knowledge"
    description = "Search your local knowledge base using the R2R system. Use this for relevant text chunks or knowledge graph data."
    inputs = {
        "query": {
            "type": "string",
            "description": "User query to search in the local DB.",
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


class SmolSearchFileKnowledgeToolR2RWrapper(R2RTool):
    def __init__(self):
        super().__init__(
            name="smol_search_file_knowledge",
            description="Wrapper for the SmolSearchFileKnowledgeTool to be used in R2R",
            results_function=self.execute,
        )
        self._r2r_tool = SearchFileKnowledgeTool()
        self._smol_tool = SmolSearchFileKnowledgeTool(
            context=self, r2r_tool=self._r2r_tool
        )

    async def execute(self, query: str, **kwargs):
        logger.debug(
            f"Executing SmolSearchFileKnowledgeToolR2RWrapper with query: {query}"
        )
        return await self._r2r_tool.execute(query)
