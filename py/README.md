<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
  <a href="https://gurubase.io/g/r2r"><img src="https://img.shields.io/badge/Gurubase-Ask%20R2R%20Guru-006BFF" alt="Gurubase: R2R Guru"></a>
</p>

<img width="1041" alt="r2r" src="https://github.com/user-attachments/assets/b6ee6a78-5d37-496d-ae10-ce18eee7a1d6">
<h3 align="center">
  Containerized, state of the art Retrieval-Augmented Generation (RAG) with a RESTful API
</h3>

# About
R2R (RAG to Riches) is the most advanced AI retrieval system, supporting Retrieval-Augmented Generation (RAG) with production-ready features. Built around a containerized [RESTful API]([https://r2r-docs.sciphi.ai/api-reference/introduction](https://r2r-docs.sciphi.ai/api-and-sdks/introduction)), R2R offers multimodal content ingestion, hybrid search functionality, configurable GraphRAG, and comprehensive user and document management.

For a more complete view of R2R, check out the [full documentation](https://r2r-docs.sciphi.ai/).

## Key Features
- [**📁 Multimodal Ingestion**](https://r2r-docs.sciphi.ai/documentation/configuration/ingestion): Parse `.txt`, `.pdf`, `.json`, `.png`, `.mp3`, and more.
- [**🔍 Hybrid Search**](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search): Combine semantic and keyword search with reciprocal rank fusion for enhanced relevancy.
- [**🔗 Knowledge Graphs**](https://r2r-docs.sciphi.ai/cookbooks/knowledge-graphs): Automatically extract entities and relationships and build knowledge graphs.
- [**📊 GraphRAG**](https://r2r-docs.sciphi.ai/cookbooks/graphrag): Cluster and summarize communities with over your created graphs for even richer insights.
- [**🗂️ User Management**](https://r2r-docs.sciphi.ai/cookbooks/user-auth): Efficiently manage documents and user roles within R2R.
- [**🔭 Observability**](https://r2r-docs.sciphi.ai/cookbooks/observability): Observe and analyze your RAG engine performance.
- [**🧩 Configuration**](https://r2r-docs.sciphi.ai/documentation/configuration/overview): Setup your application using intuitive configuration files.
- [**🖥️ Dashboard**](https://r2r-docs.sciphi.ai/cookbooks/application): An open-source React+Next.js admin dashboard to interact with R2R via GUI.


## [What's New](https://r2r-docs.sciphi.ai/introduction/whats-new)

- Release 3.3.0&nbsp;&nbsp;&nbsp;&nbsp;December 3, 2024&nbsp;&nbsp;&nbsp;&nbsp;

  Warning: These changes are breaking!
  - [V3 API Specification](https://r2r-docs.sciphi.ai/api-and-sdks/introduction)

## Install with pip
The recommended way to get started with R2R is by using our CLI.

```bash
pip install r2r
```


You may run R2R directly from the python package, but additional dependencies like Postgres+pgvector must be configured and the full R2R core is required:

```bash
# export OPENAI_API_KEY=sk-...
# export POSTGRES...
pip install 'r2r[core,ingestion-bundle]'
r2r --config-name=default serve
```

Alternatively, R2R can be launched alongside its requirements inside Docker:

```bash
# export OPENAI_API_KEY=sk-...
r2r serve --docker --full
```

The command above will install the `full` installation which includes Hatchet for orchestration and Unstructured.io for parsing.

## Getting Started

- [Installation](https://r2r-docs.sciphi.ai/documentation/installation/overview): Quick installation of R2R using Docker or pip
- [Quickstart](https://r2r-docs.sciphi.ai/documentation/quickstart): A quick introduction to R2R's core features
- [Setup](https://r2r-docs.sciphi.ai/documentation/configuration/overview): Learn how to setup and configure R2R
- [API & SDKs](https://r2r-docs.sciphi.ai/api-and-sdks/introduction): API reference and Python/JS SDKs for interacting with R2R

## Cookbooks

- Advanced RAG Pipelines
  - [RAG Agent](https://r2r-docs.sciphi.ai/cookbooks/agent): R2R's powerful RAG agent
  - [Hybrid Search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search): Introduction to hybrid search
  - [Advanced RAG](https://r2r-docs.sciphi.ai/cookbooks/advanced-rag): Advanced RAG features

- Orchestration
  - [Orchestration](https://r2r-docs.sciphi.ai/cookbooks/orchestration): R2R event orchestration

- User Management
  - [Web Development](https://r2r-docs.sciphi.ai/cookbooks/web-dev): Building webapps using R2R
  - [User Auth](https://r2r-docs.sciphi.ai/cookbooks/user-auth): Authenticating users
  - [Collections](https://r2r-docs.sciphi.ai/cookbooks/collections): Document collections
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
