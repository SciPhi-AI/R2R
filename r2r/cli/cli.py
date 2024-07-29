from r2r.cli.command_group import cli
from r2r.cli.commands import (
    auth_operations,
    document_operations,
    oberservability_operations,
    rag_operations,
    server_operations,
)

# Server operations
cli.add_command(server_operations.docker_down)
cli.add_command(server_operations.generate_report)
cli.add_command(server_operations.health)
cli.add_command(server_operations.serve)
cli.add_command(server_operations.update)
cli.add_command(server_operations.version)

# Document operations
cli.add_command(document_operations.delete)
cli.add_command(document_operations.document_chunks)
cli.add_command(document_operations.documents_overview)
cli.add_command(document_operations.ingest_files)
cli.add_command(document_operations.ingest_sample_file)
cli.add_command(document_operations.ingest_sample_files)
cli.add_command(document_operations.update_files)

# Search and RAG operations
cli.add_command(rag_operations.inspect_knowledge_graph)
cli.add_command(rag_operations.rag)
cli.add_command(rag_operations.search)

# Auth operations
cli.add_command(auth_operations.generate_private_key)

# Observability operations
cli.add_command(oberservability_operations.analytics)
cli.add_command(oberservability_operations.app_settings)
cli.add_command(oberservability_operations.logs)
cli.add_command(oberservability_operations.users_overview)


def main():
    cli()


if __name__ == "__main__":
    main()
