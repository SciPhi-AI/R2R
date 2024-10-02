from cli.command_group import cli
from cli.commands import (
    auth,
    ingestion,
    kg,
    management,
    retrieval,
    server,
    templates,
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
add_command_with_telemetry(management.document_chunks)

# Restructure
add_command_with_telemetry(kg.create_graph)
add_command_with_telemetry(kg.enrich_graph)

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

# Templates
add_command_with_telemetry(templates.clone)


def main():
    try:
        cli(_anyio_backend="asyncio")
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
