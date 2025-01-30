import json
from typing import Any

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
from cli.utils.telemetry import posthog
from r2r import R2RAsyncClient

from .command_group import CONFIG_DIR, CONFIG_FILE, load_config

console = Console()


def add_commands_with_telemetry(commands):
    """Add commands to CLI with telemetry."""
    for command in commands:
        cli.add_command(telemetry(command))


# Register commands with telemetry
commands_to_register = [
    collections.collections,
    conversations.conversations,
    documents.documents,
    graphs.graphs,
    indices.indices,
    prompts.prompts,
    retrieval.retrieval,
    users.users,
    system.system,
    database.db,
    database.upgrade,
    database.downgrade,
    database.current,
    database.history,
    config.configure,
]

add_commands_with_telemetry(commands_to_register)


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        cli()
    except SystemExit:
        pass
    except Exception as e:
        console.print("[red]CLI error: An unexpected error occurred:[/red]")
        console.print_exception()
    finally:
        if posthog:
            posthog.flush()
            posthog.shutdown()


def _ensure_config_dir_exists() -> None:
    """Ensure that the ~/.r2r/ directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_config(config_data: dict[str, Any]) -> None:
    """Persist the given config data to ~/.r2r/config.json."""
    _ensure_config_dir_exists()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


@cli.command("set-api-key", short_help="Set your R2R API key")
@click.argument("api_key", required=True, type=str)
@click.pass_context
async def set_api_key(ctx, api_key: str) -> None:
    """Store your R2R API key locally."""
    try:
        config = load_config()
        config["api_key"] = api_key
        save_config(config)
        console.print("[green]API key set successfully![/green]")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print("[red]Failed to set API key:[/red]", str(e))
    except Exception as e:
        console.print("[red]An unexpected error occurred:[/red]", str(e))


@cli.command("set-api-base", short_help="Set your R2R API base URL")
@click.argument("base_url", required=True, type=str)
@click.pass_context
async def set_api_base(ctx, base_url: str) -> None:
    """Store your R2R API base URL locally."""
    try:
        config = load_config()
        config["api_base"] = base_url
        save_config(config)
        console.print("[green]API base URL set successfully![/green]")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print("[red]Failed to set API base:[/red]", str(e))
    except Exception as e:
        console.print("[red]An unexpected error occurred:[/red]", str(e))


@cli.command("get-api", short_help="Get your stored R2R API key")
@click.pass_context
async def get_api(ctx) -> None:
    """Display your stored R2R API key."""
    try:
        config = load_config()
        api_key = config.get("api_key")

        if api_key:
            console.print(f"API Key: {api_key}")
        else:
            console.print(
                "[yellow]No API key found. Set one using 'r2r set-api <key>'[/yellow]"
            )
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print("[red]Failed to retrieve API key:[/red]", str(e))
    except Exception as e:
        console.print("[red]An unexpected error occurred:[/red]", str(e))


if __name__ == "__main__":
    main()
