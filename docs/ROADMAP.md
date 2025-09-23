# Ellen V2: Consolidated Development Roadmap

**Version**: 1.0

This document provides a consolidated, phased development plan for the Ellen V2 project, integrating milestones from all planning documents.

## Milestone 0: Foundation & Vanilla R2R (Sprint 1-2)
**Goal**: Establish the project foundation and validate the core, unmodified R2R framework with Supabase.

### Tasks
- **Project Setup**: Initialize the monorepo, configure pnpm workspaces, and create the directory structure (`apps/`, `packages/`, `supabase/`)
- **Supabase Setup**: Initialize the Supabase project, create initial database schema migrations for all tables
- **Local Environment**: Configure local Supabase environment using the Supabase CLI
- **Vanilla R2R Deployment**: Use default `docker-compose.yml` from R2R to run vanilla R2R server
- **Validation**: Use curl or Python script to upload a text file and test RAG functionality

## Milestone 1: Core Customization & MVP Frontend (Sprint 3-4)
**Goal**: Implement critical custom R2R providers and build minimal UI

### Tasks
- **Build r2r_extensions Service**: Create Dockerfile and Python package structure
- **Implement ToolAugmentedOrchestrationProvider**: Handle Text-to-SQL workflow
- **Implement HierarchicalChunkingProvider**: Implement Parent/Child chunking strategy
- **Custom Docker Compose**: Update `docker-compose.yml` to run custom R2R extensions
- **Initial Frontend**: Build basic Next.js chat interface

## Milestone 2: Advanced Ingestion & Reasoning Layer Setup (Sprint 5-6)
**Goal**: Build advanced ingestion parsers and integrate CrewAI reasoning layer

### Tasks
- **Implement StructuredDataParser**: Custom parser for Excel/CSV files
- **Implement ImageToNarrativeParser**: Custom parser for images
- **Build crewai_services App**: Set up FastAPI server for CrewAI flows
- **Build R2RKnowledgeSearchTool**: Create tool for CrewAI agents to query RAG pipeline
- **Test Flow**: Verify CrewAI agent can use R2R tool

## Milestone 3: The "Living" Platform (Sprint 7-8)
**Goal**: Automate entity updates for dynamic knowledge base

### Tasks
- **Build Initial Synthesis Engine**: Implement `entity_update_flow` for populating entities
- **Seed entity_definitions**: Add initial entity types to Supabase
- **Build Targeted Update Service**:
  - Enhance R2R ingestion with entity recognition
  - Create logic to trigger `entity_update_flow` on entity matches
- **Implement Automatic Interlinking**: Embed markdown links to related entities

## Milestone 4: Full Application & User Experience (Sprint 9-10)
**Goal**: Build full-featured frontend and prepare for alpha release

### Tasks
- **User Authentication**: Integrate Supabase Auth across frontend and backend
- **Entity-Centric UI**:
  - Create dynamic Next.js routes (`/entities/[type]/[name]`)
  - Build API endpoints for entity data
  - Develop reusable React components for entity pages
- **Advanced Flow Integration**: Build UI for triggering decision frameworks
- **UI/UX Polish**: Develop dashboard, file management, and overall UX