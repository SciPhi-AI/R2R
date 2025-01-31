import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.param_types import JSON
from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def retrieval():
    """A group of commands for retrieval operations."""
    pass


@retrieval.command()
@click.option(
    "--query",
    prompt="Enter your search query",
    help="The search query to perform the retrieval.",
)
@click.option(
    "--limit",
    default=None,
    help="Specify the maximum number of search results to return.",
)
@click.option(
    "--use-hybrid-search",
    default=None,
    help="Enable hybrid search, combining both semantic and fulltext search.",
)
@click.option(
    "--use-semantic-search",
    default=None,
    help="Enable semantic search for more contextual results.",
)
@click.option(
    "--use-fulltext-search",
    default=None,
    help="Enable fulltext search for exact matches.",
)
@click.option(
    "--filters",
    type=JSON,
    help="""Apply filters to the vector search in JSON format.
    Example: --filters='{"document_id":{"$in":["doc_id_1", "doc_id_2"]}}'""",
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Specify the search strategy (e.g., vanilla RAG or advanced methods like query fusion or HyDE).",
)
@click.option(
    "--graph-search-enabled",
    default=None,
    help="Enable knowledge graph search.",
)
@click.option(
    "--chunk-search-enabled",
    default=None,
    help="Enable search over document chunks.",
)
@pass_context
async def search(ctx: click.Context, query, **kwargs):
    """Perform a search query with the specified parameters."""
    search_settings = {
        k: v
        for k, v in kwargs.items()
        if k
        in [
            "filters",
            "limit",
            "search_strategy",
            "use_hybrid_search",
            "use_semantic_search",
            "use_fulltext_search",
        ]
        and v is not None
    }

    # Enable graph and chunk search if specified
    if kwargs.get("graph_search_enabled") is not None:
        search_settings["graph_settings"] = {
            "enabled": kwargs["graph_search_enabled"]
        }
    if kwargs.get("chunk_search_enabled") is not None:
        search_settings["chunk_settings"] = {
            "enabled": kwargs["chunk_search_enabled"]
        }

    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            results = await client.retrieval.search(
                query, "custom", search_settings
            )

            # Extract results and handle output
            if isinstance(results, dict) and "results" in results:
                results = results["results"]

            # Display chunk search results if available
            if "chunk_search_results" in results:
                click.echo("Vector search results:")
                for result in results["chunk_search_results"]:
                    click.echo(json.dumps(result, indent=2))

            # Display graph search results if available
            if (
                "graph_search_results" in results
                and results["graph_search_results"]
            ):
                click.echo("KG search results:")
                for result in results["graph_search_results"]:
                    click.echo(json.dumps(result, indent=2))
    except R2RException as e:
        click.echo(f"R2R Error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@retrieval.command()
@click.option(
    "--query",
    prompt="Enter your search query",
    help="The search query for RAG.",
)
@click.option(
    "--limit",
    default=None,
    help="Specify the number of search results to return.",
)
@click.option(
    "--use-hybrid-search",
    default=None,
    help="Enable hybrid search, combining both semantic and fulltext search.",
)
@click.option(
    "--use-semantic-search", default=None, help="Enable semantic search."
)
@click.option(
    "--use-fulltext-search", default=None, help="Enable fulltext search."
)
@click.option(
    "--filters",
    type=JSON,
    help="""Apply filters to the vector search in JSON format.
    Example: --filters='{"document_id":{"$in":["doc_id_1", "doc_id_2"]}}'""",
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Specify the search strategy for RAG.",
)
@click.option(
    "--graph-search-enabled",
    default=None,
    help="Enable knowledge graph search.",
)
@click.option(
    "--chunk-search-enabled",
    default=None,
    help="Enable search over document chunks.",
)
@click.option(
    "--stream", is_flag=True, help="Stream the RAG response in real-time."
)
@click.option(
    "--rag-model", default=None, help="Specify the model to use for RAG."
)
@pass_context
async def rag(ctx: click.Context, query, **kwargs):
    """Perform a RAG query with the specified parameters."""
    # Prepare RAG generation configuration
    rag_generation_config = {
        "stream": kwargs.get("stream", False),
    }
    if kwargs.get("rag_model"):
        rag_generation_config["model"] = kwargs["rag_model"]

    # Prepare search settings similar to the search command
    search_settings = {
        k: v
        for k, v in kwargs.items()
        if k
        in [
            "filters",
            "limit",
            "search_strategy",
            "use_hybrid_search",
            "use_semantic_search",
            "use_fulltext_search",
        ]
        and v is not None
    }

    # Enable graph and chunk search if specified
    if kwargs.get("graph_search_enabled") is not None:
        search_settings["graph_settings"] = {
            "enabled": kwargs["graph_search_enabled"]
        }
    if kwargs.get("chunk_search_enabled") is not None:
        search_settings["chunk_settings"] = {
            "enabled": kwargs["chunk_search_enabled"]
        }

    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.retrieval.rag(
                query=query,
                rag_generation_config=rag_generation_config,
                search_settings=search_settings,
            )

            # Handle streaming response
            if rag_generation_config.get("stream"):
                async for chunk in response:
                    click.echo(chunk, nl=False)
                click.echo()
            else:
                click.echo(
                    json.dumps(response["results"]["completion"], indent=2)
                )
    except R2RException as e:
        click.echo(f"R2R Error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@retrieval.command()
@click.option(
    "--message",
    prompt="Enter your message for the agent",
    help='The message to send to the agent. You can either provide a JSON string (e.g. \'{"role": "user", "content": "Hello"}\') '
    "or plain text (which will be wrapped with a default role 'user').",
)
@click.option(
    "--stream", is_flag=True, help="Stream the agent response in real-time."
)
@click.option(
    "--rag-model", default=None, help="Specify the model to use for RAG."
)
# Options for search settings (if you want to influence the underlying search call)
@click.option(
    "--limit",
    default=None,
    help="Specify the maximum number of search results to return.",
)
@click.option(
    "--use-hybrid-search",
    default=None,
    help="Enable hybrid search, combining both semantic and fulltext search.",
)
@click.option(
    "--use-semantic-search", default=None, help="Enable semantic search."
)
@click.option(
    "--use-fulltext-search", default=None, help="Enable fulltext search."
)
@click.option(
    "--filters",
    type=JSON,
    help=(
        "Apply filters to the vector search in JSON format. "
        'Example: --filters=\'{"document_id": {"$in": ["doc_id_1", "doc_id_2"]}}\''
    ),
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Specify the search strategy for agent.",
)
@click.option(
    "--graph-search-enabled",
    default=None,
    help="Enable knowledge graph search.",
)
@click.option(
    "--chunk-search-enabled",
    default=None,
    help="Enable search over document chunks.",
)
# Agent-specific options
@click.option(
    "--task-prompt-override",
    default=None,
    help="Override the default task prompt for the agent.",
)
@click.option(
    "--include-title",
    is_flag=True,
    default=False,
    help="Include the title if available.",
)
@click.option(
    "--conversation-id",
    default=None,
    help="Conversation ID to maintain context between turns.",
)
@click.option(
    "--tools",
    type=JSON,
    default=None,
    help='Provide a list of tools as JSON. Example: --tools=\'[{"name": "tool1", "config": {...}}]\'',
)
@click.option(
    "--max-tool-context-length",
    default=None,
    type=int,
    help="Maximum context length for any tool.",
)
@click.option(
    "--use-system-context/--no-use-system-context",
    default=True,
    help="Whether to use system context for the conversation.",
)
@pass_context
async def agent(
    ctx: click.Context,
    message,
    stream,
    rag_model,
    limit,
    use_hybrid_search,
    use_semantic_search,
    use_fulltext_search,
    filters,
    search_strategy,
    graph_search_enabled,
    chunk_search_enabled,
    task_prompt_override,
    include_title,
    conversation_id,
    tools,
    max_tool_context_length,
    use_system_context,
):
    """
    Perform a single turn in a conversation with a RAG agent.
    This command sends a message (optionally along with search settings) and prints the agent’s response.
    """
    # Build the rag generation configuration
    rag_generation_config = {"stream": stream}
    if rag_model:
        rag_generation_config["model"] = rag_model

    # Build search settings from the provided options
    search_settings = {
        k: v
        for k, v in {
            "filters": filters,
            "limit": limit,
            "search_strategy": search_strategy,
            "use_hybrid_search": use_hybrid_search,
            "use_semantic_search": use_semantic_search,
            "use_fulltext_search": use_fulltext_search,
        }.items()
        if v is not None
    }
    if graph_search_enabled is not None:
        search_settings["graph_settings"] = {"enabled": graph_search_enabled}
    if chunk_search_enabled is not None:
        search_settings["chunk_settings"] = {"enabled": chunk_search_enabled}

    # Attempt to parse the provided message as JSON; if that fails, wrap it with a default role.
    try:
        message_data = json.loads(message)
    except Exception:
        message_data = {"role": "user", "content": message}

    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.retrieval.agent(
                message=message_data,
                rag_generation_config=rag_generation_config,
                search_settings=search_settings,
                task_prompt_override=task_prompt_override,
                include_title_if_available=include_title,
                conversation_id=conversation_id,
                tools=tools,
                max_tool_context_length=max_tool_context_length,
                use_system_context=use_system_context,
            )
            if stream:
                async for chunk in response:
                    click.echo(chunk, nl=False)
                click.echo()  # new line after streaming completes
            else:
                # Assuming a list of messages is returned; print them nicely.
                for msg in response:
                    click.echo(json.dumps(msg, indent=2))
    except R2RException as e:
        click.echo(f"R2R Error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@retrieval.command()
@click.option(
    "--message",
    prompt="Enter your message for RAWR",
    help='The message to send for the RAWR endpoint. Provide a JSON string (e.g. \'{"role": "user", "content": "Hello"}\') '
    "or plain text (which will be wrapped with a default role 'user').",
)
@click.option(
    "--stream", is_flag=True, help="Stream the RAWR response in real-time."
)
@click.option(
    "--rag-model", default=None, help="Specify the model to use for RAWR."
)
@click.option(
    "--conversation-id",
    default=None,
    help="Conversation ID to maintain context between turns.",
)
@click.option(
    "--tools",
    type=JSON,
    default=None,
    help='Provide a list of tools as JSON. Example: --tools=\'[{"name": "tool1", "config": {...}}]\'',
)
@click.option(
    "--max-tool-context-length",
    default=None,
    type=int,
    help="Maximum context length for any tool.",
)
@pass_context
async def rawr(
    ctx: click.Context,
    message,
    stream,
    rag_model,
    conversation_id,
    tools,
    max_tool_context_length,
):
    """
    Perform a RAWR turn with the RAG agent.
    This command sends a message (without additional search settings) and prints the RAWR response.
    """
    # Build the rag generation configuration
    rag_generation_config = {"stream": stream}
    if rag_model:
        rag_generation_config["model"] = rag_model

    # Attempt to parse the provided message as JSON; if that fails, wrap it with a default role.
    try:
        message_data = json.loads(message)
    except Exception:
        message_data = {"role": "user", "content": message}

    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.retrieval.rawr(
                message=message_data,
                rag_generation_config=rag_generation_config,
                conversation_id=conversation_id,
                tools=tools,
                max_tool_context_length=max_tool_context_length,
            )
            if stream:
                async for chunk in response:
                    click.echo(chunk, nl=False)
                click.echo()
            else:
                # Assuming a list of messages is returned; print them nicely.
                for msg in response:
                    click.echo(json.dumps(msg, indent=2))
    except R2RException as e:
        click.echo(f"R2R Error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
