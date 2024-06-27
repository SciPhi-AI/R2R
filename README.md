<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

<img src="./assets/r2r.png" alt="R2R Answer Engine">
<h3 align="center">
The ultimate open source RAG answer engine
</h3>

# About
R2R was designed to bridge the gap between local LLM experimentation and scalable, production-ready Retrieval-Augmented Generation (RAG). R2R provides a comprehensive and SOTA RAG system for developers, built around a RESTful API for ease of use.

For a more complete view of R2R, check out the [full documentation](https://r2r-docs.sciphi.ai/).

## Key Features
- **📁 Multimodal Support**: Ingest files ranging from `.txt`, `.pdf`, `.json` to `.png`, `.mp3`, and more.
- **🔍 Hybrid Search**: Combine semantic and keyword search with reciprocal rank fusion for enhanced relevancy.
- **🔗 Graph RAG**: Automatically extract relationships and build knowledge graphs.
- **🗂️ App Management**: Efficiently manage documents and users with rich observability and analytics.
- **🌐 Client-Server**: RESTful API support out of the box.
- **🧩 Configurable**: Provision your application using intuitive configuration files.
- **🔌 Extensible**: Develop your application further with easy builder + factory pattern.
- **🖥️ Dashboard**: Use the [R2R Dashboard](https://github.com/SciPhi-AI/R2R-Dashboard), an open-source React+Next.js app for a user-friendly interaction with R2R.

## Table of Contents
1. [Install](#install)
2. [R2R Quickstart](#r2r-quickstart)
3. [R2R Dashboard](#r2r-dashboard)
4. [Community and Support](#community-and-support)
5. [Contributing](#contributing)

# Install

> [!NOTE]
> Windows users are advised to use Docker to run R2R.

<details open>
<summary><b>Installing with Pip</b>&nbsp;🐍 </summary>

```bash
pip install r2r

# setup env
export OPENAI_API_KEY=sk-...
export POSTGRES_USER=YOUR_POSTGRES_USER
export POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD
export POSTGRES_HOST=YOUR_POSTGRES_HOST
export POSTGRES_PORT=YOUR_POSTGRES_PORT
export POSTGRES_DBNAME=YOUR_POSTGRES_DBNAME
```
<details>
<summary><b>Installing with Docker</b>&nbsp;🐳</summary>

Note: The R2R client must still be installed, even when running with Docker. Download the Python client with `pip install r2r`.

To run R2R using Docker:

```bash
# Setting up the environment. The right side is where you should put the value of your variable.
export OPENAI_API_KEY=sk-...
export POSTGRES_USER=YOUR_POSTGRES_USER
export POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD
export POSTGRES_HOST=YOUR_POSTGRES_HOST
export POSTGRES_PORT=YOUR_POSTGRES_PORT
export POSTGRES_DBNAME=YOUR_POSTGRES_DBNAME

# Optional on first pull. Advised when fetching the main updates.
docker pull emrgntcmplxty/r2r:main

# Runs the image. If you set up the environment you don't need to modify anything.
# Otherwise, add your values on the right side of the -e commands.
# For Windows, remove the "\" from your command.
docker run -d \
   --name r2r \
   -p 8000:8000 \
   -e POSTGRES_USER=$POSTGRES_USER \
   -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
   -e POSTGRES_HOST=$POSTGRES_HOST \
   -e POSTGRES_PORT=$POSTGRES_PORT \
   -e POSTGRES_DBNAME=$POSTGRES_DBNAME \
   -e OPENAI_API_KEY=$OPENAI_API_KEY \
   emrgntcmplxty/r2r:main
```

**Important:** The Docker image of r2r operates in server and client mode, with the server being the Docker container and the client being your PC. This means you need to append `--client_server_mode` to all your queries.

Additionally, your PC (acting as the client) needs to have Python, Pip, and the dependencies listed in the r2r folder of the repository. Therefore, you need to have the repository cloned on your computer and run `pip install r2r` in the root folder of the cloned repository.

You have the option to run the client inside the terminal of the Docker container (to have everything in one place), but the use of `pip install r2r` and `--client_server_mode` is necessary.

For local LLMs:

```bash
docker run -d \
   --name r2r \
   --add-host=host.docker.internal:host-gateway \
   -p 8000:8000 \
   -e POSTGRES_USER=$POSTGRES_USER \
   -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
   -e POSTGRES_HOST=$POSTGRES_HOST \
   -e POSTGRES_PORT=$POSTGRES_PORT \
   -e POSTGRES_DBNAME=$POSTGRES_DBNAME \
   -e OLLAMA_API_BASE=http://host.docker.internal:11434 \
   -e CONFIG_OPTION=local_ollama \
  emrgntcmplxty/r2r:main
```
</details>

# Updates
Star R2R on GitHub by clicking "Star" in the upper right hand corner of the page to be instantly notified of new releases.


# R2R Quickstart
The following quickstart offers a step-by-step guide on running R2R locally as well as through the Python SDK. The guide ingests a list of provided provided documents and shows search, RAG, and advanced functionality. The script powering the quickstart can be found at `r2r/examples/quickstart.py`, and it can be configured and extended with sufficient developer familiarity.

![quickstart](https://github.com/SciPhi-AI/R2R/blob/main/assets/quickstart.gif)

<details open>
<summary><b>Document Ingestion and Management</b></summary>

1. **Ingest Files**:
   ```bash
   python -m r2r.examples.quickstart ingest_files
   ```

2. **View Document Info**:
   ```bash
   python -m r2r.examples.quickstart documents_overview
   ```

3. **View User Overview**:
   ```bash
   python -m r2r.examples.quickstart users_overview
   ```
</details>

<details open>
<summary><b>Search and RAG Operations</b></summary>

1. **Search Documents**:
   ```bash
   python -m r2r.examples.quickstart search --query="Who was Aristotle?"
   ```

2. **RAG Completion**:
   ```bash
   python -m r2r.examples.quickstart rag --query="What was Uber's profit in 2020?"
   ```

3. **Streaming RAG**:
   ```bash
   python -m r2r.examples.quickstart rag --query="What was Lyft's profit in 2020?" --stream=true
   ```

4. **Hybrid Search RAG**:
   ```bash
   python -m r2r.examples.quickstart rag --query="Who is John Snow?" --do_hybrid_search
   ```
</details>

For more detailed examples and advanced features, please refer to our [Quickstart Guide](https://r2r-docs.sciphi.ai/quickstart).

# R2R Dashboard

Interact with R2R using our [open-source React+Next.js dashboard](https://github.com/SciPhi-AI/R2R-Dashboard). Check out the [Dashboard Cookbook](https://r2r-docs.sciphi.ai/cookbooks/dashboard) to get started!

# Community and Support

- [Discord](https://discord.gg/p6KqD2kjtB): Chat live with maintainers and community members
- [Github Issues](https://github.com/SciPhi-AI/R2R/issues): Report bugs and request features

**Explore our [R2R Docs](https://r2r-docs.sciphi.ai/) for tutorials and cookbooks on various R2R features and integrations, including:**

### RAG Cookbooks
- [Multiple LLMs](https://r2r-docs.sciphi.ai/cookbooks/multiple-llms): A simple cookbook showing how R2R supports multiple LLMs.
- [Hybrid Search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search): A brief introduction to running hybrid search with R2R.
- [Multimodal RAG](https://r2r-docs.sciphi.ai/cookbooks/multimodal): A cookbook on multimodal RAG with R2R.
- [Knowledge Graphs](https://r2r-docs.sciphi.ai/cookbooks/knowledge-graph): A walkthrough of automatic knowledge graph generation with R2R.
- [Local RAG](https://r2r-docs.sciphi.ai/cookbooks/local-rag): A quick cookbook demonstration of how to run R2R with local LLMs.
- [Reranking](https://r2r-docs.sciphi.ai/cookbooks/rerank-search): A short guide on how to apply reranking to R2R results.

### App Features
- [Client-Server](https://r2r-docs.sciphi.ai/cookbooks/client-server): An extension of the basic `R2R Quickstart` with client-server interactions.
- [Document Management](https://r2r-docs.sciphi.ai/cookbooks/document-management): A cookbook showing how to manage your documents with R2R.
- [Analytics & Observability](https://r2r-docs.sciphi.ai/cookbooks/observablity): A cookbook showing R2Rs end to end logging and analytics.
- [Dashboard](https://r2r-docs.sciphi.ai/cookbooks/dashboard): A how-to guide on connecting with the R2R Dashboard.

# Contributing

We welcome contributions of all sizes! Here's how you can help:

- Open a PR for new features, improvements, or better documentation.
- Submit a [feature request](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=feature_request.md&title=) or [bug report](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=bug_report.md&title=)

### Our Contributors
<a href="https://github.com/SciPhi-AI/R2R/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SciPhi-AI/R2R" />
</a>