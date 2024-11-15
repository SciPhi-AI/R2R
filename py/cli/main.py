from cli.command_group import cli

# TODO: Remove old commands in a later release
from cli.commands.v2 import (
    ingestion,
    kg,
    management,
    server,
    retrieval as v2_retrieval,
)
from cli.commands import (
    database,
    # V3 methods
    collections,
    conversations,
    documents,
    indices,
    prompts,
    retrieval,
    system,
    users,
)
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


# Deprecated commands
# Ingestion
add_command_with_telemetry(ingestion.ingest_files)  # Deprecated
add_command_with_telemetry(ingestion.update_files)  # Deprecated
add_command_with_telemetry(
    ingestion.ingest_sample_file
)  # TODO: migrate to new schema
add_command_with_telemetry(
    ingestion.ingest_sample_files
)  # TODO: migrate to new schema
add_command_with_telemetry(
    ingestion.ingest_sample_files_from_unstructured
)  # TODO: migrate to new schema

# Management
add_command_with_telemetry(management.analytics)  # Deprecated
add_command_with_telemetry(
    management.app_settings
)  # TODO: migrate to new schema
add_command_with_telemetry(management.users_overview)  # Deprecated
add_command_with_telemetry(management.documents_overview)  # Deprecated
add_command_with_telemetry(management.list_document_chunks)  # Deprecated
add_command_with_telemetry(management.document_chunks)  # Deprecated

# Knowledge Graph
add_command_with_telemetry(kg.create_graph)  # TODO: migrate to new schema
add_command_with_telemetry(kg.enrich_graph)  # TODO: migrate to new schema
add_command_with_telemetry(
    kg.deduplicate_entities
)  # TODO: migrate to new schema

# Retrieval
add_command_with_telemetry(v2_retrieval.search)  # Deprecated
add_command_with_telemetry(v2_retrieval.rag)  # Deprecated

# Server
add_command_with_telemetry(server.server_stats)  # Deprecated
add_command_with_telemetry(server.logs)  # Deprecated

# Database
add_command_with_telemetry(database.db)
add_command_with_telemetry(database.upgrade)
add_command_with_telemetry(database.downgrade)
add_command_with_telemetry(database.current)
add_command_with_telemetry(database.history)


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
