from cli.command_group import cli
from cli.commands import (
    auth,
    ingestion,
    management,
    restructure,
    retrieval,
    server,
)

# Auth
cli.add_command(auth.generate_private_key)

# Ingesetion
cli.add_command(ingestion.ingest_files)
cli.add_command(ingestion.update_files)
cli.add_command(ingestion.ingest_sample_file)
cli.add_command(ingestion.ingest_sample_files)

# Management
cli.add_command(management.analytics)
cli.add_command(management.app_settings)
cli.add_command(management.users_overview)
cli.add_command(management.documents_overview)
cli.add_command(management.document_chunks)
cli.add_command(management.inspect_knowledge_graph)

# Restructure
cli.add_command(restructure.enrich_graph)

# Retrieval
cli.add_command(retrieval.search)
cli.add_command(retrieval.rag)

# Server
cli.add_command(server.health)
cli.add_command(server.server_stats)
cli.add_command(server.logs)
cli.add_command(server.docker_down)
cli.add_command(server.generate_report)
cli.add_command(server.serve)
cli.add_command(server.update)
cli.add_command(server.version)


def main():
    cli()


if __name__ == "__main__":
    main()
