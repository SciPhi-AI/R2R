import json
from typing import Any, Dict

import asyncclick as click
from rich.console import Console

from cli.command_group import cli
from cli.commands import (
    collections,
    config,
    conversations,
    database,
    documents,
    graphs,
    indices,
    prompts,
    retrieval,
    system,
    users,
)
from cli.utils.telemetry import posthog, telemetry
from r2r import R2RAsyncClient

from .command_group import CONFIG_DIR, CONFIG_FILE, load_config

console = Console()


def add_command_with_telemetry(command):
    cli.add_command(telemetry(command))


# Chunks
add_command_with_telemetry(collections.collections)
add_command_with_telemetry(conversations.conversations)
add_command_with_telemetry(documents.documents)
add_command_with_telemetry(graphs.graphs)

# Graph
add_command_with_telemetry(indices.indices)
add_command_with_telemetry(prompts.prompts)
add_command_with_telemetry(retrieval.retrieval)
add_command_with_telemetry(users.users)
add_command_with_telemetry(system.system)


# Database
add_command_with_telemetry(database.db)
add_command_with_telemetry(database.upgrade)
add_command_with_telemetry(database.downgrade)
add_command_with_telemetry(database.current)
add_command_with_telemetry(database.history)

add_command_with_telemetry(config.configure)


def main():
    try:
        cli()
    except SystemExit:
        pass
    except Exception as e:
        console.print("[red]CLI error: An error occurred[/red]")
        console.print_exception()
    finally:
        if posthog:
            posthog.flush()
            posthog.shutdown()


def _ensure_config_dir_exists() -> None:
    """Ensure that the ~/.r2r/ directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_config(config_data: Dict[str, Any]) -> None:
    """
    Persist the given config data to ~/.r2r/config.json.
    """
    _ensure_config_dir_exists()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


@cli.command("set-api-key", short_help="Set your R2R API key")
@click.argument("api_key_key", required=True, type=str)
@click.pass_context
async def set_api_key(ctx, api_key: str):
    """
    Store your R2R API key locally so you don’t have to pass it on every command.
    Example usage:
      r2r set-api sk-1234abcd
    """
    try:
        # 1) Load existing config
        config = load_config()

        # 2) Overwrite or add the API key
        config["api_key"] = api_key

        # 3) Save changes
        save_config(config)

        console.print("[green]API key set successfully![/green]")
    except Exception as e:
        console.print("[red]Failed to set API key:[/red]", str(e))


@cli.command("get-api", short_help="Get your stored R2R API key")
@click.pass_context
async def get_api(ctx):
    """
    Display your stored R2R API key.
    Example usage:
      r2r get-api
    """
    try:
        config = load_config()
        api_key = config.get("api_key")

        if api_key:
            console.print(f"API Key: {api_key}")
        else:
            console.print(
                "[yellow]No API key found. Set one using 'r2r set-api <key>'[/yellow]"
            )
    except Exception as e:
        console.print("[red]Failed to retrieve API key:[/red]", str(e))


if __name__ == "__main__":
    main()
