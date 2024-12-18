from cli.command_group import cli
from cli.commands import (
    collections,
    conversations,
    config,
    database,
    documents,
    graphs,
    indices,
    prompts,
    retrieval,
    system,
    users,
)

from rich.console import Console
from cli.utils.telemetry import posthog, telemetry

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


if __name__ == "__main__":
    main()
