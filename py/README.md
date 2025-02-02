![Screenshot 2025-01-30 at 5 11 34 PM](https://github.com/user-attachments/assets/16d32b31-4c7d-4e84-be19-24574b33527b)




<h3 align="center">
The most advanced AI retrieval system.

Agentic Retrieval-Augmented Generation (RAG) with a RESTful API.
</h3>

<div align="center">
   <div>
      <h3>
         <a href="https://app.sciphi.ai">
            <strong>Sign up</strong>
         </a> ·
         <a href="https://r2r-docs.sciphi.ai/self-hosting/installation/overview">
            <strong>Self Host</strong>
      </h3>
   </div>
   <div>
      <a href="https://r2r-docs.sciphi.ai/"><strong>Docs</strong></a> ·
      <a href="https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=bug_report.md&title="><strong>Report Bug</strong></a> ·
      <a href="https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=feature_request.md&title="><strong>Feature Request</strong></a> ·
      <a href="https://discord.gg/p6KqD2kjtB"><strong>Discord</strong></a>
   </div>
   <br />
   <p align="center">
    <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
    <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
    <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
    <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
    <a href="https://gurubase.io/g/r2r"><img src="https://img.shields.io/badge/Gurubase-Ask%20R2R%20Guru-006BFF" alt="Gurubase: R2R Guru"></a>
  </p>
</div>

# About
R2R (Reason to Retrieve) is the most advanced AI retrieval system, supporting Retrieval-Augmented Generation (RAG) with production-ready features. Built around a containerized RESTful API, R2R offers multimodal content ingestion, hybrid search functionality, knowledge graphs, and comprehensive user and document management.

For a more complete view of R2R, check out the [full documentation](https://r2r-docs.sciphi.ai/).


## Getting Started

### [SciPhi Cloud](https://app.sciphi.ai)

Access R2R through a deployment managed by the SciPhi team, which includes a generous free-tier. No credit card required.

## Local

Install and run R2R:

```bash
# Install the R2R package
pip install r2r

# Set necessary environment variables
export OPENAI_API_KEY=sk-...

# Run the server and database
r2r serve --docker --full

# Refer to docs for local LLM setup - https://r2r-docs.sciphi.ai/self-hosting/local-rag
```

## Key Features

### Ingestion & Retrieval

- **📁 [Multimodal Ingestion](https://r2r-docs.sciphi.ai/self-hosting/configuration/ingestion)**
  Parse `.txt`, `.pdf`, `.json`, `.png`, `.mp3`, and more.
- **🔍 [Hybrid Search](https://r2r-docs.sciphi.ai/documentation/search-and-rag)**
  Combine semantic and keyword search with reciprocal rank fusion for enhanced relevancy.
- **🔗 [Knowledge Graphs](https://r2r-docs.sciphi.ai/cookbooks/graphs)**
  Automatically extract entities and relationships to build knowledge graphs.
- **🤖 [Agentic RAG](https://r2r-docs.sciphi.ai/documentation/retrieval/rawr)**
  R2R's powerful reasoning agent integrated with RAG.


### Application Layer

- 💻 **[Web Development](https://r2r-docs.sciphi.ai/cookbooks/web-dev)**
  Building web apps using R2R.
- 🔐 **[User Auth](https://r2r-docs.sciphi.ai/documentation/user-auth)**
  Authenticating users.
- 📂 **[Collections](https://r2r-docs.sciphi.ai/self-hosting/collections)**
  Document collections management.
- 🌐 **[Web Application](https://r2r-docs.sciphi.ai/cookbooks/web-dev)**
  Connecting with the R2R Application.

### Self-Hosting

- 🐋 **[Docker](/self-hosting/installation/full/docker)**
  Use Docker to easily deploy the full R2R system into your local environment
- 🧩 ** [Configuration](https://r2r-docs.sciphi.ai/self-hosting/configuration/overview)**
  Set up your application using intuitive configuration files.

## Community

[Join our Discord](https://discord.gg/p6KqD2kjtB) to get support and connect with both the R2R team and other developers in the community. Whether you're encountering issues, looking for advice on best practices, or just want to share your experiences, we're here to help.

## Contributing

We welcome contributions of all sizes! Here's how you can help:

- Open a PR for new features, improvements, or better documentation.
- Submit a [feature request](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=feature_request.md&title=) or [bug report](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=bug_report.md&title=)

### Our Contributors
<a href="https://github.com/SciPhi-AI/R2R/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SciPhi-AI/R2R" />
</a>
