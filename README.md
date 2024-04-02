# R2R: Production-ready RAG systems.

<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

<img src="./docs/pages/r2r.png" alt="Sciphi Framework">
R2R, short for RAG to Riches, is a Python framework designed for the rapid development of production-ready Retrieval-Augmented Generation (RAG) systems. It offers the fastest and most efficient way to serve a RAG pipeline to end users. The framework is built around customizeable pipelines and a featureful FastAPI implementation.

R2R is to NextJS what LangChain/LlamaIndex are to React.
## Demo(s)

Using cloud application to deploy the pre-built basic pipeline:
https://www.loom.com/share/e3b934b554484787b005702ced650ac9

Note - the example above uses [SciPhi Cloud](https://app.sciphi.ai) to pair with the R2R framework for observability and optimization. We intend on launching a self-hosted version of the cloud framework as our codebase matures.

### Quick Install:

**Install R2R directly using `pip`:**

```bash
# use the `'r2r[all]'` to download all required deps
pip install 'r2r[parsing,eval]'

# setup env 
export OPENAI_API_KEY=sk-...
# Set `LOCAL_DB_PATH` for local testing
export LOCAL_DB_PATH=local.sqlite

# OR do `vim .env.example && cp .env.example .env`
# INCLUDE secrets and modify config.json
# if using cloud providers (e.g. pgvector, qdrant, ...)
```

## Links

[Join the Discord server](https://discord.gg/p6KqD2kjtB)

[R2R Docs Quickstart](https://r2r-docs.sciphi.ai/getting-started/quick-install)

## Basic Example

[`basic_pipeline.py`](r2r/examples/servers/basic_pipeline.py): Running this script launches the default backend server with a basic RAG pipeline, which includes the ingestion, embedding, and RAG pipelines served via FastAPI.

   ```bash
   # launch the server
   python -m r2r.examples.servers.basic_pipeline
   ```

[`run_basic_client.py`](r2r/examples/clients/run_basic_client.py): The client should be ran after starting the basic pipeline server. It demonstrates uploading text entries and a PDF to the local server using the Python client. It also showcases document and user-level vector management with built-in features.

   ```bash
   # run the client
   python -m r2r.examples.clients.run_basic_client
   ```

## Synthetic Queries Example

[`synthetic_query_pipeline.py`](r2r/examples/servers/synthetic_query_pipeline.py): Running this script launches the default backend server with a more advanced pipeline that generates synthetic queries to improve the RAG pipeline's performance.

   ```bash
   # launch the server
   python -m r2r.examples.servers.synthetic_query_pipeline
   ```

[`run_synthetic_query_client.py`](r2r/examples/clients/run_synthetic_query_client.py): This client example is optimized for interaction with the synthetic query pipeline server, showcasing the enhanced RAG pipeline's capabilities.

   ```bash
   # run the client
   python -m r2r.examples.clients.run_synthetic_query_client
   ```

## Extras Examples

[`reducto_pipeline.py`](r2r/examples/servers/reducto_pipeline.py): Running this script launches the default backend server with a Reducto adapter for PDF ingestion.

   ```bash
   # launch the server
   python -m r2r.examples.servers.reducto_pipeline
   ```

[`web_search_pipeline.py`](r2r/examples/servers/web_search_pipeline.py): Running this script launches the default backend server with a `WebSearchRAGPipeline` for web search capabilities.

   ```bash
   # launch the server
   python -m r2r.examples.servers.web_search_pipeline
   ```

## Core Abstractions

The framework primarily revolves around three core abstractions:

- The **Ingestion Pipeline**: Facilitates the preparation of embeddable 'Documents' from various data formats (json, txt, pdf, html, etc.). The abstraction can be found in [`ingestion.py`](r2r/core/pipelines/ingestion.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/core-features/ingestion).

- The **Embedding Pipeline**: Manages the transformation of text into stored vector embeddings, interacting with embedding and vector database providers through a series of steps (e.g., extract_text, transform_text, chunk_text, embed_chunks, etc.). The abstraction can be found in [`embedding.py`](r2r/core/pipelines/embedding.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/core-features/embedding).

- The **RAG Pipeline**: Works similarly to the embedding pipeline but incorporates an LLM provider to produce text completions. The abstraction can be found in [`rag.py`](r2r/core/pipelines/rag.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/core-features/rag).

- The **Eval Pipeline**: Samples some subset of rag_completion calls for evaluation. Currently [DeepEval](https://github.com/confident-ai/deepeval) is supported. The abstraction can be found in [`eval.py`](r2r/core/pipelines/eval.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/core-features/eval).

Each pipeline incorporates a logging database for operation tracking and observability.


## Key Features

- **🚀 Deploy**: production-ready RAG pipelines with streaming in seconds
- **🧩 Customize**: your pipeline using intuitive configuration files
- **🔌 Extend**: your pipeline logic with code
- **⚖️ Autoscale**: your pipeline in the cloud with [SciPhi](https://app.sciphi.ai/) 
- **🤖 OSS**: framework built for and by the OSS community to make RAG easier.

