# type: ignore
from typing import AsyncGenerator

import orgparse

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class ORGParser(AsyncParser[str | bytes]):
    """Parser for ORG (Emacs Org-mode) files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.orgparse = orgparse

    def _process_node(self, node) -> list[str]:
        """Process an org-mode node and return its content."""
        contents = []

        # Add heading with proper level of asterisks
        if node.level > 0:
            contents.append(f"{'*' * node.level} {node.heading}")

        # Add body content if exists
        if node.body:
            contents.append(node.body.strip())

        return contents

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest ORG data and yield document content."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        try:
            # Create a temporary file-like object for orgparse
            from io import StringIO

            file_obj = StringIO(data)

            # Parse the org file
            root = self.orgparse.load(file_obj)

            # Process root node if it has content
            if root.body:
                yield root.body.strip()

            # Process all nodes
            for node in root[1:]:  # Skip root node in iteration
                contents = self._process_node(node)
                for content in contents:
                    if content.strip():
                        yield content.strip()

        except Exception as e:
            raise ValueError(f"Error processing ORG file: {str(e)}") from e
        finally:
            file_obj.close()
