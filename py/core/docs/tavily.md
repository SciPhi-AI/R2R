# Tavily Search and URL Extraction

This document provides information on using Tavily's search and URL extraction capabilities with R2R.

## Setup

1. Sign up for a Tavily API key at [https://tavily.com](https://tavily.com)
2. Add the API key to your environment file:
   ```
   TAVILY_API_KEY=your_api_key_here
   ```
3. Ensure the `tavily-python` package is installed. It's already included in the `core` dependencies of the R2R project.

## Using Tavily Tools

There are two Tavily tools available:

### 1. tavily_search

This tool performs web searches using Tavily's search API and returns relevant results.

Features:
- Advanced search capabilities with high-quality content retrieval
- Optional answer generation by the Tavily API
- Ability to include or exclude specific domains
- Both basic and advanced search depth options

### 2. tavily_extract

This tool extracts and parses the content from a specific URL using Tavily's extraction API.

Features:
- Clean, structured content extraction from web pages
- Metadata extraction including page title and other information
- Useful for analyzing the full content of a specific webpage

## Configuration

To enable Tavily tools in your R2R configuration, update your config file:

```toml
[agent]
rag_tools = [
    "search_file_descriptions",
    "search_file_knowledge",
    "get_file_content",
    "tavily_search",
    "tavily_extract"
]
```

Alternatively, use the provided `tavily.toml` configuration file:

```bash
r2r-serve --config-name tavily
```

## Tips for Effective Usage

- Keep Tavily search queries concise (under 400 characters) for better results
- For complex research, consider breaking down into multiple focused searches
- URL extraction is most useful for detailed page analysis when you need the full content
- Consider using tavily_search first to find relevant URLs, then tavily_extract to get full page content

## Example Use Cases

- Research on specific topics where you need high-quality web results
- Extracting content from documentation pages or articles for analysis
- Building knowledge bases from web content
- Fact-checking or retrieving the latest information on a topic