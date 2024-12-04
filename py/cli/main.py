from cli.command_group import cli
from cli.commands import (  # V3 methods
    collections,
    conversations,
    database,
    documents,
    indices,
    prompts,
    retrieval,
    system,
    users,
    graphs,
)

# TODO: Remove old commands in a later release
from cli.utils.telemetry import posthog, telemetry


def add_command_with_telemetry(command):
    cli.add_command(telemetry(command))


# Chunks
add_command_with_telemetry(collections.collections)
add_command_with_telemetry(conversations.conversations)
add_command_with_telemetry(documents.documents)
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

add_command_with_telemetry(graphs.graphs)  # Added this line


def main():
    try:
        cli()
    except SystemExit:
        # Silently exit without printing the traceback
        pass
    except Exception as e:
        # Handle other exceptions if needed
        print("CLI error: An error occurred")
        raise e
    finally:
        # Ensure all events are flushed before exiting
        if posthog:
            posthog.flush()
            posthog.shutdown()


if __name__ == "__main__":
    main()
