"""Anonymous web search using Parallel's Streamable HTTP MCP server."""

import asyncio
import json
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation

SEARCH_MCP_URL = "https://search.parallel.ai/mcp"
USER_AGENT = "R2R (https://github.com/SciPhi-AI/R2R)"
SEARCH_TIMEOUT = 30


async def search_parallel(query: str) -> list[dict]:
    """Return organic results compatible with R2R's existing web result model.

    Use a bounded, anonymous session. Errors propagate to the agent's tool error
    handling; they must never trigger a switch to another search provider.
    """
    try:
        return await asyncio.wait_for(_search(query), timeout=SEARCH_TIMEOUT)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"Parallel Search MCP timed out after {SEARCH_TIMEOUT} seconds"
        ) from exc


async def _search(query: str) -> list[dict]:
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(SEARCH_TIMEOUT),
        follow_redirects=False,
    ) as client:
        async with streamable_http_client(
            SEARCH_MCP_URL, http_client=client
        ) as (read, write, _):
            async with ClientSession(
                read,
                write,
                client_info=Implementation(name="R2R", version="3.6.6"),
            ) as session:
                await session.initialize()
                response = await session.call_tool(
                    "web_search",
                    arguments={"objective": query, "search_queries": [query]},
                )

    if response.isError:
        raise RuntimeError("Parallel Search MCP returned a tool error")

    data = response.structuredContent
    if data is None:
        text = "\n".join(
            block.text for block in response.content if block.type == "text"
        )
        data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError("Invalid Parallel Search MCP results")

    results = []
    for position, item in enumerate(data["results"], start=1):
        if not isinstance(item, dict):
            raise ValueError("Invalid Parallel Search MCP result")
        url = item.get("url")
        excerpts = item.get("excerpts", [])
        if (
            not isinstance(url, str)
            or urlsplit(url).scheme not in ("http", "https")
            or not urlsplit(url).hostname
            or not isinstance(excerpts, list)
            or any(not isinstance(excerpt, str) for excerpt in excerpts)
        ):
            raise ValueError("Invalid Parallel Search MCP URL or excerpts")
        results.append(
            {
                "type": "organic",
                "title": item.get("title") or url,
                "link": url,
                "snippet": "\n".join(excerpts),
                "position": position,
            }
        )
    return results
