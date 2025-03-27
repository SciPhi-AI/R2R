# type: ignore
import re
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class JSParser(AsyncParser[str | bytes]):
    """A parser for JavaScript files."""

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
        """Ingest JavaScript data and yield structured text representation.

        Extracts functions, classes, variable declarations, comments, and other
        important structures from JavaScript code in a text format suitable for analysis.

        :param data: The JavaScript content to parse
        :param kwargs: Additional keyword arguments
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        # Process the JavaScript content
        processed_text = self._process_js_content(data)

        # Yield the processed text
        yield processed_text

    def _process_js_content(self, js: str) -> str:
        """Process JavaScript content into a structured text representation.

        This method:
        1. Extracts and preserves comments
        2. Identifies imports and exports
        3. Extracts function and class definitions
        4. Identifies variable declarations
        5. Formats the JavaScript structure in a readable way
        """
        # Extract comments
        comments = self._extract_comments(js)

        # Extract imports and exports
        imports_exports = self._extract_imports_exports(js)

        # Extract function definitions
        functions = self._extract_functions(js)

        # Extract class definitions
        classes = self._extract_classes(js)

        # Extract variable declarations
        variables = self._extract_variables(js)

        # Build the result
        result = []

        if comments:
            result.append("COMMENTS:")
            result.extend(comments)
            result.append("")

        if imports_exports:
            result.append("IMPORTS AND EXPORTS:")
            result.extend(imports_exports)
            result.append("")

        if functions:
            result.append("FUNCTIONS:")
            result.extend(functions)
            result.append("")

        if classes:
            result.append("CLASSES:")
            result.extend(classes)
            result.append("")

        if variables:
            result.append("VARIABLE DECLARATIONS:")
            result.extend(variables)
            result.append("")

        return "\n".join(result)

    def _extract_comments(self, js: str) -> list[str]:
        """Extract comments from JavaScript content."""
        # Extract multi-line comments
        multiline_pattern = r"/\*(.*?)\*/"
        multiline_comments = re.findall(multiline_pattern, js, re.DOTALL)

        # Extract single-line comments
        singleline_pattern = r"//(.+)$"
        singleline_comments = re.findall(singleline_pattern, js, re.MULTILINE)

        comments = []
        # Add multi-line comments
        for comment in multiline_comments:
            formatted_comment = comment.strip()
            if formatted_comment:
                comments.append(formatted_comment)

        # Add single-line comments
        for comment in singleline_comments:
            formatted_comment = comment.strip()
            if formatted_comment:
                comments.append(formatted_comment)

        return comments

    def _extract_imports_exports(self, js: str) -> list[str]:
        """Extract import and export statements."""
        # Remove comments to simplify parsing
        js_without_comments = self._remove_comments(js)

        # Match import statements
        import_pattern = r"import\s+.*?;|import\s+.*?\s+from\s+.*?;"
        imports = re.findall(import_pattern, js_without_comments)

        # Match export statements
        export_pattern = (
            r"export\s+.*?;|export\s+default\s+.*?;|export\s+\{.*?\};"
        )
        exports = re.findall(export_pattern, js_without_comments)

        results = []
        for stmt in imports + exports:
            results.append(stmt.strip())

        return results

    def _extract_functions(self, js: str) -> list[str]:
        """Extract function definitions."""
        # Remove comments to simplify parsing
        js_without_comments = self._remove_comments(js)

        results = []

        # Match regular function declarations
        func_pattern = r"function\s+(\w+)\s*\([^)]*\)\s*\{[^{]*\}"
        funcs = re.finditer(func_pattern, js_without_comments)
        for func in funcs:
            # Get the function signature
            signature = func.group(0)
            # Extract just the function declaration line
            declaration = re.search(r"function\s+\w+\s*\([^)]*\)", signature)
            if declaration:
                results.append(declaration.group(0))

        # Match arrow functions with explicit names
        arrow_pattern = (
            r"(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=;]*)\s*=>\s*\{?"
        )
        arrows = re.finditer(arrow_pattern, js_without_comments)
        for arrow in arrows:
            results.append(arrow.group(0))

        # Match method definitions in objects and classes
        method_pattern = r"(\w+)\s*\([^)]*\)\s*\{"
        methods = re.finditer(method_pattern, js_without_comments)
        for method in methods:
            # Filter out if/for/while statements
            if not re.match(r"(if|for|while|switch)\s*\(", method.group(0)):
                results.append(method.group(0))

        return results

    def _extract_classes(self, js: str) -> list[str]:
        """Extract class definitions."""
        # Remove comments to simplify parsing
        js_without_comments = self._remove_comments(js)

        results = []

        # Match class declarations
        class_pattern = r"class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{"
        classes = re.finditer(class_pattern, js_without_comments)
        for cls in classes:
            results.append(cls.group(0))

        # Match class expressions
        class_expr_pattern = (
            r"(?:const|let|var)\s+(\w+)\s*=\s*class(?:\s+\w+)?\s*\{"
        )
        class_exprs = re.finditer(class_expr_pattern, js_without_comments)
        for cls_expr in class_exprs:
            results.append(cls_expr.group(0))

        return results

    def _extract_variables(self, js: str) -> list[str]:
        """Extract variable declarations."""
        # Remove comments to simplify parsing
        js_without_comments = self._remove_comments(js)

        # Match variable declarations (excluding function/class assignments)
        var_pattern = r"(?:const|let|var)\s+\w+(?:\s*=\s*[^=>{].*?)?;"
        vars_raw = re.finditer(var_pattern, js_without_comments)

        results = []
        for var in vars_raw:
            var_text = var.group(0).strip()
            # Skip function/arrow function assignments which are handled separately
            if not re.search(r"=\s*function|\s*=>\s*", var_text):
                results.append(var_text)

        return results

    def _remove_comments(self, js: str) -> str:
        """Remove comments from JavaScript code to simplify parsing."""
        # Remove multi-line comments
        js = re.sub(r"/\*.*?\*/", "", js, flags=re.DOTALL)
        # Remove single-line comments
        js = re.sub(r"//.*?$", "", js, flags=re.MULTILINE)
        return js
