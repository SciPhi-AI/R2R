"""Exercise web search through the RAG registry, dispatcher and MCP transport."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.agent.rag import R2RRAGAgent
from core.base.abstractions import (
    GenerationConfig,
    LLMChatCompletion,
    Message,
    SearchSettings,
)
from core.base.agent.agent import RAGAgentConfig
from core.utils import parallel_search
from core.utils.serper import SerperClient


def make_agent(tools=None, include_tools=True):
    return R2RRAGAgent(
        database_provider=MagicMock(),
        llm_provider=MagicMock(),
        config=RAGAgentConfig(
            rag_tools=["web_search"] if tools is None else tools,
            include_tools=include_tools,
        ),
        search_settings=SearchSettings(),
        rag_generation_config=GenerationConfig(model="test/model"),
        knowledge_search_method=AsyncMock(),
        content_method=AsyncMock(),
        file_search_method=AsyncMock(),
    )


@pytest.fixture(autouse=True)
def no_search_credentials(monkeypatch):
    for key in (
        "SERPER_API_KEY",
        "R2R_WEB_SEARCH_PROVIDER",
        "PARALLEL_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def mcp_transport(monkeypatch):
    requests = []
    state = {
        "data": {
            "results": [
                {
                    "title": "R2R research",
                    "url": "https://example.org/research?q=rag&year=2026",
                    "excerpts": [
                        "A current research source",
                        "A second excerpt",
                    ],
                }
            ]
        },
        "structured": False,
        "error": False,
    }

    async def handler(request):
        requests.append(request)
        if request.method != "POST":
            return httpx.Response(405)
        body = json.loads(request.content)
        method = body["method"]
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": body["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "web_search",
                        "description": "Search",
                        "inputSchema": {"type": "object"},
                    }
                ]
            }
        elif method == "tools/call":
            if state.get("exception"):
                raise state["exception"]
            if state.get("wait"):
                state["started"].set()
                await asyncio.Event().wait()
            result = {
                "content": [
                    {"type": "text", "text": json.dumps(state["data"])}
                ],
                "isError": state["error"],
            }
            if state["structured"]:
                result["structuredContent"] = state["data"]
        else:
            raise AssertionError(method)
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": result}
        )

    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(parallel_search.httpx, "AsyncClient", client_factory)
    return SimpleNamespace(requests=requests, state=state)


async def dispatch(agent):
    return await agent.handle_function_or_tool_call(
        "web_search",
        json.dumps({"query": "recent retrieval research"}),
        tool_id="search-1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("structured", [False, True])
async def test_anonymous_search_reaches_agent_and_collector(
    mcp_transport, structured
):
    mcp_transport.state["structured"] = structured
    agent = make_agent()
    result = await dispatch(agent)
    assert (
        "A current research source\nA second excerpt"
        in result.llm_formatted_result
    )
    assert (
        "https://example.org/research?q=rag&year=2026"
        in result.llm_formatted_result
    )
    assert "Source ID [" in result.llm_formatted_result
    assert (
        result.raw_result.web_search_results[0].organic_results[0].title
        == "R2R research"
    )
    assert agent.search_results_collector.get_all_results()
    page = result.raw_result.web_search_results[0].organic_results[0]
    source = agent.search_results_collector.find_by_short_id(str(page.id)[:7])
    assert source["link"] == page.link
    assert source["snippet"] == page.snippet
    messages = await agent.conversation.get_messages()
    assert messages[-1]["content"] == result.llm_formatted_result
    assert messages[-1]["tool_call_id"] == "search-1"
    calls = []
    for request in mcp_transport.requests:
        assert str(request.url) == parallel_search.SEARCH_MCP_URL
        assert request.headers["User-Agent"] == parallel_search.USER_AGENT
        assert "authorization" not in request.headers
        if request.method == "POST":
            calls.append(json.loads(request.content))
    assert any(call["method"] == "initialize" for call in calls)
    search_call = next(
        call for call in calls if call["method"] == "tools/call"
    )
    assert search_call["params"]["name"] == "web_search"
    assert search_call["params"]["arguments"] == {
        "objective": "recent retrieval research",
        "search_queries": ["recent retrieval research"],
    }


@pytest.mark.asyncio
async def test_scripted_model_consumes_search_in_agent_loop(mcp_transport):
    """Scripted model responses exercise arun without paid model inference."""
    agent = make_agent()
    calls = 0

    async def completion(messages, config):
        nonlocal calls
        calls += 1
        if calls == 1:
            assert config.tools[0]["function"]["name"] == "web_search"
            message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "search-1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": json.dumps(
                                {"query": "recent retrieval research"}
                            ),
                        },
                    }
                ],
            }
            finish = "tool_calls"
        else:
            assert messages[-1]["role"] == "tool"
            assert "A current research source" in messages[-1]["content"]
            assert (
                "https://example.org/research?q=rag&year=2026"
                in messages[-1]["content"]
            )
            source = agent.search_results_collector.get_all_results()[0][1]
            sid = str(source.id)[:7]
            assert (
                agent.search_results_collector.find_by_short_id(sid)["link"]
                == source.link
            )
            message = {
                "role": "assistant",
                "content": f"Research source [{sid}]",
            }
            finish = "stop"
        return LLMChatCompletion(
            id=f"scripted-{calls}",
            created=0,
            model="test/model",
            object="chat.completion",
            choices=[
                {"index": 0, "finish_reason": finish, "message": message}
            ],
        )

    agent.llm_provider.aget_completion = completion
    messages = await agent.arun(
        messages=[Message(role="user", content="Find recent research")],
        system_instruction="Use web search when needed.",
    )
    assert calls == 2
    assert messages[-1]["content"].startswith("Research source [")


@pytest.mark.asyncio
async def test_configured_serper_is_preserved(monkeypatch, mcp_transport):
    monkeypatch.setenv("SERPER_API_KEY", "configured")
    with patch.object(SerperClient, "get_raw", return_value=[]) as serper:
        result = await dispatch(make_agent())
    serper.assert_called_once_with("recent retrieval research")
    assert result.raw_result.web_search_results[0].organic_results == []
    assert mcp_transport.requests == []


@pytest.mark.asyncio
async def test_explicit_parallel_overrides_serper(monkeypatch, mcp_transport):
    monkeypatch.setenv("SERPER_API_KEY", "configured")
    monkeypatch.setenv("R2R_WEB_SEARCH_PROVIDER", "parallel")
    with patch.object(
        SerperClient, "get_raw", side_effect=AssertionError("Serper selected")
    ):
        result = await dispatch(make_agent())
    assert "A current research source" in result.llm_formatted_result


@pytest.mark.asyncio
async def test_explicit_serper_does_not_fall_back(monkeypatch, mcp_transport):
    monkeypatch.setenv("R2R_WEB_SEARCH_PROVIDER", "serper")
    result = await dispatch(make_agent())
    assert "SERPER_API_KEY" in result.llm_formatted_result
    assert mcp_transport.requests == []


@pytest.mark.asyncio
async def test_serper_error_does_not_fall_back(monkeypatch, mcp_transport):
    monkeypatch.setenv("SERPER_API_KEY", "configured")
    with patch.object(
        SerperClient, "get_raw", side_effect=RuntimeError("provider failed")
    ):
        result = await dispatch(make_agent())
    assert "provider failed" in result.llm_formatted_result
    assert mcp_transport.requests == []


@pytest.mark.asyncio
async def test_invalid_provider_is_an_error(monkeypatch, mcp_transport):
    monkeypatch.setenv("R2R_WEB_SEARCH_PROVIDER", "unknown")
    result = await dispatch(make_agent())
    assert "must be auto, parallel, or serper" in result.llm_formatted_result
    assert mcp_transport.requests == []


@pytest.mark.asyncio
async def test_disabled_tools_and_permissions(mcp_transport):
    agent = make_agent(tools=[])
    assert agent.tools == []
    assert (
        await agent.execute_tool("web_search", query="test")
        == "Error: Tool web_search not found."
    )
    agent = make_agent(include_tools=False)
    assert agent.get_generation_config({"role": "user"}).tools is None
    assert mcp_transport.requests == []
    assert "web_search" not in RAGAgentConfig().rag_tools


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_data",
    [
        {},
        {"results": "invalid"},
        {"results": ["invalid"]},
        {"results": [{"url": "file:///etc/passwd"}]},
        {"results": [{"url": "https://example.org", "excerpts": "invalid"}]},
    ],
)
async def test_malformed_results_are_tool_errors(mcp_transport, bad_data):
    mcp_transport.state["data"] = bad_data
    result = await dispatch(make_agent())
    assert "failed with an exception" in result.llm_formatted_result
    assert "Invalid Parallel" in result.llm_formatted_result


@pytest.mark.asyncio
async def test_remote_tool_error_is_reported(mcp_transport):
    mcp_transport.state["error"] = True
    result = await dispatch(make_agent())
    assert "returned a tool error" in result.llm_formatted_result


@pytest.mark.asyncio
async def test_transport_error_is_reported(mcp_transport):
    mcp_transport.state["exception"] = httpx.ReadTimeout("timed out")
    result = await dispatch(make_agent())
    assert "failed with an exception" in result.llm_formatted_result


@pytest.mark.asyncio
async def test_timeout_and_cancellation(mcp_transport, monkeypatch):
    mcp_transport.state.update(wait=True, started=asyncio.Event())
    monkeypatch.setattr(parallel_search, "SEARCH_TIMEOUT", 0.05)
    with pytest.raises(
        asyncio.TimeoutError, match="Parallel Search MCP timed out"
    ):
        await make_agent().execute_tool("web_search", query="test")
    monkeypatch.setattr(parallel_search, "SEARCH_TIMEOUT", 30)
    mcp_transport.state["started"].clear()
    task = asyncio.create_task(dispatch(make_agent()))
    await asyncio.wait_for(mcp_transport.state["started"].wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
