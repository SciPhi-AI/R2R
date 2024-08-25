<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

<img width="1041" alt="r2r" src="https://github.com/user-attachments/assets/b6ee6a78-5d37-496d-ae10-ce18eee7a1d6">
<h3 align="center">
Build, scale, and manage user-facing Retrieval-Augmented Generation applications in production.
</h3>

# About
R2R (RAG to Riches), the Supabase for RAG, bridges the gap between experimenting with and deploying production-ready Retrieval-Augmented Generation (RAG) applications. It's a complete platform that helps you quickly build and launch scalable RAG solutions. R2R is built around a simple [RESTful API](https://r2r-docs.sciphi.ai/api-reference/introduction), making it easy to use and fast to implement.

For a more complete view of R2R, check out the [full documentation](https://r2r-docs.sciphi.ai/).

## Key Features
- **📁 Multimodal Support**: Ingest files ranging from `.txt`, `.pdf`, `.json` to `.png`, `.mp3`, and more.
- **🔍 Hybrid Search**: Combine semantic and keyword search with reciprocal rank fusion for enhanced relevancy.
- **🔗 Graph RAG**: Automatically extract relationships and build knowledge graphs.
- **🗂️ App Management**: Efficiently manage documents and users with full authentication.
- **🔭 Observability**: Observe and analyze your RAG engine performance.
- **🧩 Configurable**: Provision your application using intuitive configuration files.
- **🔌 Extensibility**: Develop your application further with easy builder + factory pattern.
- **🖥️ Dashboard**: Use the [R2R Dashboard](https://github.com/SciPhi-AI/R2R-Dashboard), an open-source React+Next.js app with optional authentication, to interact with R2R via GUI.


## Getting Started

- [Installation](https://r2r-docs.sciphi.ai/documentation/installation): Quick installation of R2R using Docker or pip
- [Quickstart](https://r2r-docs.sciphi.ai/documentation/quickstart): A quick introduction to R2R's core features


## Install with pip
The recommended way to get started with R2R is by using our CLI.

```bash
pip install r2r
```

Then, after installing R2R, it is recommended to launch with Docker, if possible:

```bash
# export OPENAI_API_KEY=sk-...
r2r serve --docker
```

Alternatively, you may run R2R directly from the python package, but additional dependencies like Postgres+pgvector must be configured and the full R2R core is required:

```bash
# export OPENAI_API_KEY=sk-...
# export POSTGRES...
pip install 'r2r[core]'
r2r --config-name=default serve
```



## Getting Started

- [Installation](https://r2r-docs.sciphi.ai/documentation/installation): Quick installation of R2R using Docker or pip
- [Quickstart](https://r2r-docs.sciphi.ai/documentation/quickstart): A quick introduction to R2R's core features

## API & SDKs

- [SDK](https://r2r-docs.sciphi.ai/documentation/python-sdk): API reference and Python/JS SDKs for interacting with R2R
- [API](https://r2r-docs.sciphi.ai/api-reference/introduction): API reference and Python/JS SDKs for interacting with R2R
- [Configuration](/documentation/configuration): A guide on how to configure your R2R system

## Cookbooks

- Advanced RAG Pipelines
  - [RAG Agent](https://r2r-docs.sciphi.ai/cookbooks/agent): R2R's powerful RAG agent
  - [Hybrid Search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search): Introduction to hybrid search
  - [Advanced RAG](https://r2r-docs.sciphi.ai/cookbooks/advanced-rag): Advanced RAG features

- Knowledge Graphs
  - [GraphRAG](https://r2r-docs.sciphi.ai/cookbooks/graphrag): Walkthrough of GraphRAG
  - [Knowledge Graphs](https://r2r-docs.sciphi.ai/cookbooks/knowledge-graph): Automatic knowledge graph generation

- Auth & Admin Features
  - [Web Development](https://r2r-docs.sciphi.ai/cookbooks/web-dev): Building webapps using R2R
  - [User Auth](https://r2r-docs.sciphi.ai/cookbooks/user-auth): Authenticating users
  - [Group Permissions](https://r2r-docs.sciphi.ai/cookbooks/groups): Group permissions
  - [Analytics & Observability](https://r2r-docs.sciphi.ai/cookbooks/observability): End-to-end logging and analytics
  - [Web Application](https://r2r-docs.sciphi.ai/cookbooks/application): Connecting with the R2R Application

## Community

[Join our Discord server](https://discord.gg/p6KqD2kjtB) to get support and connect with both the R2R team and other developers in the community. Whether you're encountering issues, looking for advice on best practices, or just want to share your experiences, we're here to help.

# Contributing

We welcome contributions of all sizes! Here's how you can help:

- Open a PR for new features, improvements, or better documentation.
- Submit a [feature request](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=feature_request.md&title=) or [bug report](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=bug_report.md&title=)

### Our Contributors
<a href="https://github.com/SciPhi-AI/R2R/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SciPhi-AI/R2R" />
</a>
