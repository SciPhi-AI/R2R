# type: ignore
from typing import AsyncGenerator
import re

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class CSSParser(AsyncParser[str | bytes]):
    """A parser for CSS files."""

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
        """Ingest CSS data and yield structured text representation.
        
        Extracts selectors, properties, values, and comments from CSS while
        preserving the structure in a text format suitable for analysis.
        
        :param data: The CSS content to parse
        :param kwargs: Additional keyword arguments
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")
        
        # Process the CSS content
        processed_text = self._process_css_content(data)
        
        # Yield the processed text
        yield processed_text
    
    def _process_css_content(self, css: str) -> str:
        """Process CSS content into a structured text representation.
        
        This method:
        1. Extracts and preserves comments
        2. Identifies selectors and their properties
        3. Formats the CSS structure in a readable way
        """
        # Extract comments
        comments = self._extract_comments(css)
        
        # Extract rules (selectors and declarations)
        rules = self._extract_rules(css)
        
        # Build the result
        result = []
        
        if comments:
            result.append("COMMENTS:")
            result.extend(comments)
            result.append("")
        
        if rules:
            result.append("CSS RULES:")
            result.extend(rules)
        
        return "\n".join(result)
    
    def _extract_comments(self, css: str) -> list[str]:
        """Extract comments from CSS content."""
        comment_pattern = r'/\*(.*?)\*/'
        comments = re.findall(comment_pattern, css, re.DOTALL)
        return [comment.strip() for comment in comments if comment.strip()]
    
    def _extract_rules(self, css: str) -> list[str]:
        """Extract selectors and their declarations from CSS content."""
        # Remove comments to simplify parsing
        css_without_comments = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
        
        # Pattern to match CSS rules
        rule_pattern = r'([^{]+)\{([^}]*)\}'
        matches = re.findall(rule_pattern, css_without_comments)
        
        rules = []
        for selector, declarations in matches:
            selector = selector.strip()
            if not selector:
                continue
                
            rules.append(f"Selector: {selector}")
            
            # Process declarations
            declaration_list = declarations.strip().split(';')
            for declaration in declaration_list:
                declaration = declaration.strip()
                if declaration:
                    property_value = declaration.split(':', 1)
                    if len(property_value) == 2:
                        property_name = property_value[0].strip()
                        value = property_value[1].strip()
                        rules.append(f"  {property_name}: {value}")
            
            rules.append("")  # Empty line for readability
        
        return rules