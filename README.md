<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

<img src="./assets/r2r.png" alt="R2R Answer Engine">
<h3 align="center">
Build, scale, and manage user-facing Retrieval-Augmented Generation applications in production.
</h3>

# About
R2R was designed to bridge the gap between local LLM experimentation and scalable, production-ready Retrieval-Augmented Generation (RAG) applications. R2R provides a the latest techniques in RAG and is built around a RESTful API for ease of use.

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


## Install with pip
The recommended way to get started with R2R is by using our CLI.

```bash
pip install r2r
```

Then, after installing R2R, it is recommended to launch with Docker, if possible:

```bash
# export OPENAI_API_KEY=sk-...
r2r --config-name=default serve --docker
```

Alternatively, you may run R2R directly from the python package, but additional dependencies like Postgres+pgvector must be configured:

```bash
# export OPENAI_API_KEY=sk-...
# export POSTGRES...
r2r --config-name=default serve
```


## Quickstart
After [installing](https://r2r-docs.sciphi.ai/installation), the [R2R Quickstart](https://r2r-docs.sciphi.ai/quickstart) is your go to for a step-by-step guide to get up and running with R2R in minutes. The guide demonstrates R2R's Retrieval-Augmented Generation (RAG) system by ingesting sample documents and then showcasing features for search, RAG, logging, analytics, and document management.
## Getting Started

To get started with R2R, we recommend starting with the quickstart and then moving on to specific cookbooks.

- [Installation](https://r2r-docs.sciphi.ai/installation): Quick setup using Docker or `pip`
- [R2R Quickstart](https://r2r-docs.sciphi.ai/quickstart): A quickstart guide designed to get you familiarized with R2R.


### Auth & Admin Features
- [User Auth](https://r2r-docs.sciphi.ai/cookbooks/user-auth): A cookbook showing how to authenticate users using R2R.
- [Analytics & Observability](https://r2r-docs.sciphi.ai/cookbooks/observability): A cookbook showing R2Rs end to end logging and analytics.
- [Dashboard](https://r2r-docs.sciphi.ai/cookbooks/dashboard): A how-to guide on connecting with the R2R Admin/User Dashboard.

### RAG Cookbooks

- [Multiple LLMs](https://r2r-docs.sciphi.ai/cookbooks/multiple-llms): A simple cookbook showing how R2R supports multiple LLMs.
- [Hybrid Search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search): A brief introduction to running hybrid search with R2R.
- [Multimodal RAG](https://r2r-docs.sciphi.ai/cookbooks/multimodal): A cookbook on multimodal RAG with R2R.
- [Knowledge Graphs](https://r2r-docs.sciphi.ai/cookbooks/knowledge-graph): A walkthrough of automatic knowledge graph generation with R2R.
- [Advanced Graphs](https://r2r-docs.sciphi.ai/cookbooks/advanced-rag): A walkthrough of R2Rs advanced RAG features.
- [Local RAG](https://r2r-docs.sciphi.ai/cookbooks/local-rag): A quick cookbook demonstration of how to run R2R with local LLMs.
- [Reranking](https://r2r-docs.sciphi.ai/cookbooks/rerank-search): A short guide on how to apply reranking to R2R results.

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
