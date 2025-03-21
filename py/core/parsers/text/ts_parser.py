# type: ignore
import re
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class TSParser(AsyncParser[str | bytes]):
    """A parser for TypeScript source code files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

    async def ingest(
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest TypeScript source code and yield structured text representation.

        Extracts JSDoc comments, function/class/interface definitions, and comments while
        preserving the code structure in a text format suitable for analysis.

        :param data: The TypeScript source code to parse.
        :param kwargs: Additional keyword arguments.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        # Process the TypeScript code
        processed_text = self._process_ts_code(data)

        # Yield the processed text
        yield processed_text

    def _process_ts_code(self, code: str) -> str:
        """Process TypeScript code into a more structured text representation.

        This method:
        1. Preserves file-level JSDoc comments
        2. Extracts imports and exports
        3. Extracts class, interface, type, and function definitions with their comments
        4. Preserves TypeScript-specific type annotations
        """
        # Split into lines for processing
        lines = code.splitlines()
        result = []

        # Extract file-level comments
        file_comment = self._extract_file_comment(code)
        if file_comment:
            result.append("FILE COMMENT:")
            result.append(file_comment)
            result.append("")

        # Extract imports and exports
        imports_exports = self._extract_imports_exports(lines)
        if imports_exports:
            result.append("IMPORTS/EXPORTS:")
            result.extend(imports_exports)
            result.append("")

        # Extract definitions (class, interface, type, function)
        definitions = self._extract_definitions(code)
        if definitions:
            result.append("DEFINITIONS:")
            result.extend(definitions)

        return "\n".join(result)

    def _extract_file_comment(self, code: str) -> str:
        """Extract the file-level JSDoc comment if present."""
        # Look for JSDoc comments at the beginning of the file
        file_comment_pattern = r"^\s*/\*\*(.*?)\*/\s*"
        match = re.search(file_comment_pattern, code, re.DOTALL)
        if match:
            # Format the comment by removing asterisks and preserving content
            comment = match.group(1)
            # Clean up the comment lines
            lines = [
                line.strip().lstrip("*").strip()
                for line in comment.split("\n")
            ]
            return "\n".join(line for line in lines if line)
        return ""

    def _extract_imports_exports(self, lines: list[str]) -> list[str]:
        """Extract import and export statements from the code."""
        statements = []
        for line in lines:
            line = line.strip()
            if (
                line.startswith(("import ", "export "))
                or re.match(r"^(import|export)\s+\{", line)
            ) and not line.startswith("//"):
                statements.append(line)
        return statements

    def _extract_definitions(self, code: str) -> list[str]:
        """Extract class, interface, type, and function definitions with their comments."""
        definitions = []

        # Pattern for definitions with preceding JSDoc comments
        # This captures JSDoc comments, export keywords, and various TypeScript definitions
        pattern = r"(?:/\*\*(.*?)\*/\s*)?(?:export\s+)?(?:(class|interface|type|enum|function|const|let|var)\s+\w+[\s\S]*?(?:\{|=>|;))"

        matches = re.finditer(pattern, code, re.DOTALL)

        for match in matches:
            jsdoc = match.group(1)
            definition = match.group(2) and match.group(0)[match.start(2) :]

            if jsdoc:
                # Format the JSDoc comment
                lines = [
                    line.strip().lstrip("*").strip()
                    for line in jsdoc.split("\n")
                ]
                formatted_jsdoc = "\n".join(line for line in lines if line)
                definitions.append(formatted_jsdoc)

            if definition:
                # Extract the first line or meaningful part of the definition
                def_lines = definition.strip().split("\n")
                if len(def_lines) > 3:  # If definition is long, abbreviate
                    short_def = "\n".join(def_lines[:3]) + "\n..."
                    definitions.append(short_def)
                else:
                    definitions.append(definition.strip())

            definitions.append("")  # Add empty line for readability

        return definitions
