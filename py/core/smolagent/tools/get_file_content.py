from smolagents import Tool as SmolTool

from core.base.agent.tools.built_in.get_file_content import GetFileContentTool
from shared.abstractions.tool import Tool as R2RTool


class SmolGetFileContentTool(SmolTool):
    name = "smol_get_file_content"
    description = "Fetches the complete contents of a user document from the local database by document ID."
    inputs = {
        "document_id": {
            "type": "string",
            "description": "The unique UUID of the document to fetch.",
        }
    }
    output_type = "object"
    parameters = inputs

    def __init__(self, context, r2r_tool: R2RTool, **kwargs):
        super().__init__()
        self.context = context
        self.results_function = self.forward
        self._r2r_tool = r2r_tool

    async def forward(self, document_id: str):
        return await self._r2r_tool.execute(document_id)


class SmolGetFileContentToolR2RWrapper(R2RTool):
    def __init__(self):
        super().__init__(
            name="smol_get_file_content",
            description="Wrapper for the SmolGetFileContentTool to be used in R2R",
            results_function=self.execute,
        )
        self._r2r_tool = GetFileContentTool()
        self._smol_tool = SmolGetFileContentTool(
            context=self, r2r_tool=self._r2r_tool
        )

    async def execute(self, document_id: str, **kwargs):
        # Placeholder function, not to be used
        pass
