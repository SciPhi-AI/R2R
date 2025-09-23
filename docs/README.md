# The Ellen V2 Project

**Version**: 2.0  
**Status**: In Development

## 1. Vision & Purpose
Ellen V2 is a next-generation OODA Intelligence Platform designed to accelerate strategic decision-making. It transforms vast amounts of unstructured data (PDFs, spreadsheets, news feeds) into a structured, interconnected, and continuously evolving knowledge base.

The system operates on the core principle of "Adopt and Expand." We leverage the powerful open-source R2R (Retrieval to Riches) framework as our foundational knowledge layer and extend it with custom capabilities. For complex, multi-step reasoning, we use CrewAI as our orchestration and reasoning layer.

Users interact with Ellen via two primary interfaces:

1. **Advanced AI Chat**: For asking complex, ad-hoc questions and receiving precise, cited answers grounded in source data
2. **Structured Entity UI**: For exploring pre-synthesized "living wiki" pages on key entities (materials, companies, people) that automatically update

## 2. Core Technology Stack
| Component             | Technology                         |
|-----------------------|------------------------------------|
| Monorepo Management   | pnpm workspaces                   |
| Core RAG Engine       | R2R (Retrieval to Riches)          |
| AI Orchestration      | CrewAI (Flow feature)              |
| Database              | Supabase (PostgreSQL with pgvector)|
| Frontend              | Next.js with App Router & shadcn/ui|
| Backend Services      | Python with FastAPI                |
| Deployment            | Docker                             |

## 3. Project Structure
Monorepo with three primary applications:

| Directory              | Description                          |
|------------------------|--------------------------------------|
| `apps/frontend`        | User-facing Next.js application      |
| `apps/r2r_extensions`  | Custom providers for R2R (Knowledge Layer)|
| `apps/crewai_services` | CrewAI flows server (Reasoning Layer)|

For full architecture details, see [ARCHITECTURE.md](architecture.md).

## 4. Getting Started with Local Development
### Prerequisites
- Docker and Docker Compose
- Node.js (v18+) and pnpm
- Python (v3.11+) and Poetry
- Supabase project credentials

### Setup Instructions
1. **Clone repository**:
   ```bash
   git clone <repository_url>
   cd ellen-v2
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Install dependencies**:
   ```bash
   pnpm install
   poetry install
   ```

4. **Set up database**:
   ```bash
   npx supabase db push
   ```

5. **Run development environment**:
   ```bash
   docker-compose up --build
   ```

### Accessing Services
| Service                | URL                         |
|------------------------|-----------------------------|
| Frontend Application   | http://localhost:3000       |
| R2R API (Customized)   | http://localhost:7272       |
| CrewAI Services API    | http://localhost:8001       |
| Supabase Studio        | Supabase project dashboard  |