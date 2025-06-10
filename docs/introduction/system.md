# System Architecture

Learn about the R2R system architecture and how its components work together.

## System Overview

R2R is built on a modular, service-oriented architecture designed for scalability and flexibility. The system consists of several key layers that work together to provide advanced RAG capabilities:

### API Layer
A RESTful API handles incoming requests.

### Core Services
Specialized services handle different aspects of the system:
- **Auth Service**: Manages user authentication and authorization
- **Retrieval Service**: Handles search and RAG operations
- **Ingestion Service**: Processes and stores documents
- **Graph Builder Service**: Creates and manages knowledge graphs
- **App Management Service**: Handles application-level operations

### Orchestration
The orchestration layer manages complex workflows and long-running tasks using RabbitMQ as a message queue system, ensuring reliable processing of background jobs.

### Storage
The storage layer utilizes:
- **Postgres with pgvector**: For vector storage, full-text search, and relational data
- **File Storage**: For document and media file management, either via S3 or Postgres

### Providers
Pluggable components that can be customized and swapped:
- **Embedding Provider**: Handles text-to-vector conversion
- **LLM Provider**: Manages language model interactions
- **Auth Provider**: Customizable authentication methods
- **Ingestion Provider**: Handles document parsing and processing

### R2R Application
A React + Next.js application providing a user-friendly interface for interacting with the R2R system, allowing users to manage documents, run searches, and configure settings.

## Architecture Benefits

This modular architecture provides several key advantages:

- **Scalability**: Each service can be scaled independently based on demand
- **Flexibility**: Providers can be swapped out without affecting the core system
- **Reliability**: Message queue orchestration ensures robust handling of complex workflows
- **Extensibility**: New services and providers can be added without disrupting existing functionality

## Data Flow

The typical flow through the R2R system follows this pattern:

1. **User Request**: Users send queries through the R2R Application or directly to the API
3. **Authentication**: The Auth Service validates user credentials and permissions
4. **Service Coordination**: The Orchestrator coordinates between services using RabbitMQ
5. **Processing**: Core services (Retrieval, Ingestion, Graph Builder) process the request
6. **Provider Integration**: Services utilize appropriate providers (Embedding, LLM, etc.)
7. **Storage Operations**: Data is retrieved from or stored in Postgres, or File Storage
8. **Response**: Results are returned through the API back to the user

## Getting Started

Ready to explore R2R? Here's where to go next:

- **Quick Setup**: Check out our [Docker installation guide](../self-hosting/getting-started/installation/full.md)
- **First Steps**: Follow our [Quickstart tutorial](../documentation/getting-started/quickstart.md)
- **Deep Dive**: Learn about [What is R2R?](guides/what-is-r2r.md)

This architecture enables R2R to handle everything from simple RAG applications to complex, production-grade systems with advanced features like hybrid search and GraphRAG.
