# Ellen V2: Docker and Local Development Setup

This document provides a guide for setting up and running the Ellen V2 project locally using Docker and Docker Compose.

## 1. Overview of Services
The `docker-compose.yml` file orchestrates services required for local development:

| Service            | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `supabase`         | Supabase CLI-managed services (database, auth, storage)                     |
| `r2r_extensions`   | Custom R2R server (Knowledge Layer)                                         |
| `crewai_services`  | FastAPI server for CrewAI flows (Reasoning Layer)                           |
| `frontend`         | Next.js web application                                                     |

## 2. Environment Variables
All services are configured via `.env` file:
1. Copy `.env.example` to `.env`
2. Fill in required values:
   - `OPENAI_API_KEY`: OpenAI API key
   - Supabase credentials: `SUPABASE_PROJECT_ID`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_PASSWORD`

## 3. docker-compose.yml Specification
```yaml
version: '3.8'

services:
  r2r_extensions:
    build:
      context: ./apps/r2r_extensions
      dockerfile: Dockerfile
    container_name: ellen_r2r_extensions
    env_file: .env
    ports:
      - "7272:7272"  # R2R API port
    depends_on:
      - db  # Supabase Postgres container
    networks:
      - ellen-net

  crewai_services:
    build:
      context: ./apps/crewai_services
      dockerfile: Dockerfile
    container_name: ellen_crewai_services
    env_file: .env
    ports:
      - "8001:8000"  # FastAPI port
    depends_on:
      - r2r_extensions
    networks:
      - ellen-net

  frontend:
    build:
      context: ./apps/frontend
      dockerfile: Dockerfile
    container_name: ellen_frontend
    env_file: .env
    ports:
      - "3000:3000"
    depends_on:
      - r2r_extensions
      - crewai_services
    networks:
      - ellen-net

networks:
  ellen-net:
    driver: bridge
```

**Note**: Supabase service names may need adjustment based on CLI naming.

## 4. Supabase Local Development
Use the official Supabase CLI:
1. **Install CLI**: Follow [Supabase CLI installation instructions](https://supabase.com/docs/guides/cli)
2. **Start Services**:
   ```bash
   npx supabase start
   ```
   - Applies migrations from `supabase/migrations`
3. **Stop Services**:
   ```bash
   npx supabase stop
   ```

## 5. Running the Full Stack
1. Start Supabase:
   ```bash
   npx supabase start
   ```
2. Start application services:
   ```bash
   docker-compose up --build
   ```

Your full local development environment is now running.