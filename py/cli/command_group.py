import types
from functools import wraps
from typing import Any, Never

import asyncclick as click
from asyncclick import pass_context
from asyncclick.exceptions import Exit
from rich import box
from rich.console import Console
from rich.table import Table

from sdk import R2RAsyncClient

console = Console()


def silent_exit(ctx, code=0):
    if code != 0:
        raise Exit(code)


def deprecated_command(new_name):
    def decorator(f):
        @wraps(f)
        async def wrapped(*args, **kwargs):
            click.secho(
                f"Warning: This command is deprecated. Please use '{new_name}' instead.",
                fg="yellow",
                err=True,
            )
            return await f(*args, **kwargs)

        return wrapped

    return decorator


def custom_help_formatter(commands):
    """Create a nicely formatted help table using rich"""
    table = Table(
        box=box.ROUNDED,
        border_style="blue",
        pad_edge=False,
        collapse_padding=True,
    )

    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    command_groups = {
        "Document Management": [
            ("documents", "Document ingestion and management commands"),
            ("collections", "Collections management commands"),
        ],
        "Knowledge Graph": [
            ("graphs", "Graph creation and management commands"),
            ("prompts", "Prompt template management"),
        ],
        "Interaction": [
            ("conversations", "Conversation management commands"),
            ("retrieval", "Knowledge retrieval commands"),
        ],
        "System": [
            ("configure", "Configuration management commands"),
            ("users", "User management commands"),
            ("indices", "Index management commands"),
            ("system", "System administration commands"),
        ],
        "Database": [
            ("db", "Database management commands"),
            ("upgrade", "Upgrade database schema"),
            ("downgrade", "Downgrade database schema"),
            ("current", "Show current schema version"),
            ("history", "View schema migration history"),
        ],
    }

    for group_name, group_commands in command_groups.items():
        table.add_row(
            f"[bold yellow]{group_name}[/bold yellow]", "", style="dim"
        )
        for cmd_name, description in group_commands:
            if cmd_name in commands:
                table.add_row(f"  {cmd_name}", commands[cmd_name].help or "")
        table.add_row("", "")  # Add spacing between groups

    return table


class CustomGroup(click.Group):
    def format_help(self, ctx, formatter):
        console.print("\n[bold blue]R2R Command Line Interface[/bold blue]")
        console.print("The most advanced AI retrieval system\n")

        if self.get_help_option(ctx) is not None:
            console.print("[bold cyan]Usage:[/bold cyan]")
            console.print("  r2r [OPTIONS] COMMAND [ARGS]...\n")

        console.print("[bold cyan]Options:[/bold cyan]")
        console.print(
            "  --base-url TEXT  Base URL for the API [default: http://localhost:7272]"
        )
        console.print("  --help           Show this message and exit.\n")

        console.print("[bold cyan]Commands:[/bold cyan]")
        console.print(custom_help_formatter(self.commands))
        console.print(
            "\nFor more details on a specific command, run: [bold]r2r COMMAND --help[/bold]\n"
        )


class CustomContext(click.Context):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.exit_func = types.MethodType(silent_exit, self)

    def exit(self, code: int = 0) -> Never:
        self.exit_func(code)
        raise SystemExit(code)


@click.group(cls=CustomGroup)
@click.option(
    "--base-url", default="http://localhost:7272", help="Base URL for the API"
)
@pass_context
async def cli(ctx: click.Context, base_url: str) -> None:
    """R2R CLI for all core operations."""
    ctx.obj = R2RAsyncClient(base_url=base_url)
