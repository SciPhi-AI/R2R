# R2R: Production-ready RAG systems.

<p align="left">
  <a href="https://docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

A semi-opinionated RAG framework.

<img src="./docs/pages/r2r.png" alt="Sciphi Framework">
R2R was conceived to bridge the gap between experimental RAG models and robust, production-ready systems. Our semi-opinionated framework cuts through the complexity, offering a straightforward path to deploy, adapt, and maintain RAG pipelines in production. We prioritize simplicity and practicality, aiming to set a new industry benchmark for ease of use and effectiveness.

### Quick Install:

**Install R2R directly using `pip`:**

```bash
# use the `'r2r[all]'` to download all required deps
pip install 'r2r[parsing,eval]'
# setup env 
export OPENAI_API_KEY=sk-...
export LOCAL_DB_PATH=local.sqlite

# OR do `vim .env.example && cp .env.example .env`
```

## Links

[Join the Discord server](https://discord.gg/p6KqD2kjtB)

[Read our Docs](https://docs.sciphi.ai/)

## Basic Examples

The project includes several basic examples that demonstrate application deployment and interaction:

1. [`app.py`](examples/basic/app.py): This example runs the main application, which includes the ingestion, embedding, and RAG pipelines served via FastAPI.

   ```bash
   uvicorn r2r.examples.basic.app:app
   ```

2. [`basic client`](examples/basic/run_client.py): This example should be run after starting the main application. It demonstrates uploading text entries as well as a PDF to the local server with the python client. Further, it shows document and user-level vector management with built-in features.

   ```bash
   python -m r2r.examples.basic.run_client
   ```

3. [`pdf chat`](examples/pdf_chat/run_client.py): An example demonstrating upload and chat with a more realistic pdf.

   ```bash
   # Ingest pdf
   python -m r2r.examples.pdf_chat.run_client ingest

   # Ask a question
   python -m r2r.examples.pdf_chat.run_client search "What are the key themes of Meditations?"
   ```


4. [`academy`](examples/academy): A more sophisticated demo demonstrating how to build a more novel pipeline which involves synthetic queries

   ```bash
   # launch academy application
   uvicorn r2r.examples.academy.app:app

   # Ask a question
   python -m r2r.examples.academy.run_client search "What are the key themes of Meditations?"
   ```


4. [`web`](web/package.json): A web application which is meant to accompany the framework to provide visual intelligence.
   ```bash
   cd $workdir/web && pnpm install
   
   # Serve the web app
   pnpm dev
   ```

## Demo

[![demo_screenshot](./docs/pages/getting-started/demo_screenshot.png)](https://github.com/SciPhi-AI/R2R/assets/68796651/01fee645-1beb-4096-9e7d-7d0fa01386ea)

### Full Install:

Follow these steps to ensure a smooth setup:

1. **Install Poetry:**

   - Before installing the project, make sure you have Poetry on your system. If not, visit the [official Poetry website](https://python-poetry.org/docs/#installation) for installation instructions.

2. **Clone and Install Dependencies:**

  - Clone the project repository and navigate to the project directory:
     
     ```bash
     git clone git@github.com:SciPhi-AI/r2r.git
     cd r2r
     ```
     
  - Copy the `.env.example` file to `.env`. This file is in the main project folder:

     ```bash
     cp .env.example .env

     # Add secrets, `OPENAI_API_KEY` at a minimum
     vim .env
     ```
     
  - Install the project dependencies with Poetry:
  
     ```bash
     # See pyproject.toml for available extras
     # use "all" to include every optional dependency
     poetry install -E parsing -E eval
     ```
     
  - Execute with poetry run:
     
     ```bash
     python -m r2r.examples.pdf_chat.run_client ingest
     ```

3. **Configure Environment Variables:**
   - You need to set up cloud provider secrets in your `.env`. At a minimum, you will need an OpenAI key.
   - The framework currently supports PostgreSQL (locally), pgvector and Qdrant with plans to extend coverage.

## Key Features

- **🚀 Rapid Deployment**: Facilitates a smooth setup and development of production-ready RAG systems.
- **⚖️ Flexible Standardization**: `Ingestion`, `Embedding`, and `RAG` with proper `Observability`.
- **🧩 Easy to modify**: Provides a structure that can be extended to deploy your own custom pipelines.
- **📦 Versioning**: Ensures your work remains reproducible and traceable through version control.
- **🔌 Extensibility**: Enables a quick and robust integration with various VectorDBs, LLMs and Embeddings Models.
- **🤖 OSS Driven**: Built for and by the OSS community, to help startups and enterprises to quickly build with RAG.
- **📝 Deployment Support**: Available to help you build and deploy your RAG systems end-to-end.

## Core Abstractions

The framework primarily revolves around three core abstractions:

- The **Ingestion Pipeline**: Facilitates the preparation of embeddable 'Documents' from various data formats (json, txt, pdf, html, etc.). The abstraction can be found in [`ingestion.py`](r2r/core/pipelines/ingestion.py).

- The **Embedding Pipeline**: Manages the transformation of text into stored vector embeddings, interacting with embedding and vector database providers through a series of steps (e.g., extract_text, transform_text, chunk_text, embed_chunks, etc.). The abstraction can be found in [`embedding.py`](r2r/core/pipelines/embedding.py).

- The **RAG Pipeline**: Works similarly to the embedding pipeline but incorporates an LLM provider to produce text completions. The abstraction can be found in [`rag.py`](r2r/core/pipelines/rag.py).

- The **Eval Pipeline**: Samples some subset of rag_completion calls for evaluation. Currently [DeepEval](https://github.com/confident-ai/deepeval) is supported. The abstraction can be found in [`eval.py`](r2r/core/pipelines/eval.py).

Each pipeline incorporates a logging database for operation tracking and observability.
