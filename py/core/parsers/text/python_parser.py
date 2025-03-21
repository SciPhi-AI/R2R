# type: ignore
import re
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class PythonParser(AsyncParser[str | bytes]):
    """A parser for Python source code files."""

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
        """Ingest Python source code and yield structured text representation.

        Extracts docstrings, function/class definitions, and comments while
        preserving the code structure in a text format suitable for analysis.

        :param data: The Python source code to parse.
        :param kwargs: Additional keyword arguments.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        # Process the Python code
        processed_text = self._process_python_code(data)

        # Yield the processed text
        yield processed_text

    def _process_python_code(self, code: str) -> str:
        """Process Python code into a more structured text representation.

        This method:
        1. Preserves module-level docstrings
        2. Extracts class and function definitions with their docstrings
        3. Preserves comments and code structure
        4. Removes unnecessary whitespace
        """
        # Split into lines for processing
        lines = code.splitlines()
        result = []

        # Extract module docstring if present
        module_docstring = self._extract_module_docstring(code)
        if module_docstring:
            result.append("MODULE DOCSTRING:")
            result.append(module_docstring)
            result.append("")

        # Extract imports
        imports = self._extract_imports(lines)
        if imports:
            result.append("IMPORTS:")
            result.extend(imports)
            result.append("")

        # Extract class and function definitions with docstrings
        definitions = self._extract_definitions(code)
        if definitions:
            result.append("DEFINITIONS:")
            result.extend(definitions)

        return "\n".join(result)

    def _extract_module_docstring(self, code: str) -> str:
        """Extract the module-level docstring if present."""
        module_docstring_pattern = r'^"""(.*?)"""'
        match = re.search(module_docstring_pattern, code, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try single quotes if double quotes not found
        module_docstring_pattern = r"^'''(.*?)'''"
        match = re.search(module_docstring_pattern, code, re.DOTALL)
        if match:
            return match.group(1).strip()

        return ""

    def _extract_imports(self, lines: list[str]) -> list[str]:
        """Extract import statements from the code."""
        imports = []
        for line in lines:
            line = line.strip()
            if line.startswith(("import ", "from ")) and not line.startswith(
                "#"
            ):
                imports.append(line)
        return imports

    def _extract_definitions(self, code: str) -> list[str]:
        """Extract class and function definitions with their docstrings."""
        definitions = []

        # Pattern for class and function definitions
        def_pattern = r'((?:def|class)\s+\w+(?:\(.*?\))?\s*(?:->.*?)?:)(?:\s*"""(.*?)"""|\s*\'\'\'(.*?)\'\'\')?'
        matches = re.finditer(def_pattern, code, re.DOTALL)

        for match in matches:
            definition = match.group(1).strip()
            docstring = match.group(2) or match.group(3)

            definitions.append(definition)
            if docstring:
                # Format the docstring with indentation
                formatted_docstring = "\n".join(
                    f"  {line.strip()}"
                    for line in docstring.strip().split("\n")
                )
                definitions.append(formatted_docstring)

            definitions.append("")  # Add empty line for readability

        return definitions
