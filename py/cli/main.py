from cli.command_group import cli
from cli.commands import (
    auth,
    database,
    ingestion,
    kg,
    management,
    retrieval,
    server,
)
from cli.utils.telemetry import posthog, telemetry


def add_command_with_telemetry(command):
    cli.add_command(telemetry(command))


# Auth
add_command_with_telemetry(auth.generate_private_key)

# Ingestion
add_command_with_telemetry(ingestion.ingest_files)
add_command_with_telemetry(ingestion.update_files)
add_command_with_telemetry(ingestion.ingest_sample_file)
add_command_with_telemetry(ingestion.ingest_sample_files)
add_command_with_telemetry(ingestion.ingest_sample_files_from_unstructured)

# Management
add_command_with_telemetry(management.analytics)
add_command_with_telemetry(management.app_settings)
add_command_with_telemetry(management.users_overview)
add_command_with_telemetry(management.documents_overview)
add_command_with_telemetry(management.list_document_chunks)

# Knowledge Graph
add_command_with_telemetry(kg.create_graph)
add_command_with_telemetry(kg.enrich_graph)
add_command_with_telemetry(kg.deduplicate_entities)

# Retrieval
add_command_with_telemetry(retrieval.search)
add_command_with_telemetry(retrieval.rag)

# Server
add_command_with_telemetry(server.health)
add_command_with_telemetry(server.server_stats)
add_command_with_telemetry(server.logs)
add_command_with_telemetry(server.docker_down)
add_command_with_telemetry(server.generate_report)
add_command_with_telemetry(server.serve)
add_command_with_telemetry(server.update)
add_command_with_telemetry(server.version)

# Database
add_command_with_telemetry(database.db)  # Add the main db group
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
