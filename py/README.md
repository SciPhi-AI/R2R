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


## Key Features
- [**📁 Multimodal Ingestion**](https://r2r-docs.sciphi.ai/documentation/documents): Support for over 26 files types, including `.txt`, `.pdf`, `.json`, `.png`, `.mp3`, and more.
- [**🔍 Hybrid Search**](https://r2r-docs.sciphi.ai/documentation/hybrid-search): Combine semantic and keyword search with reciprocal rank fusion for enhanced relevancy.
- [**🔗 Knowledge Graphs**](https://r2r-docs.sciphi.ai/cookbooks/graphs): Automatically extract entities and relationships, build knowledge graphs, and run GraphRAG.
- [**🗂️ User Management**](https://r2r-docs.sciphi.ai/self-hosting/user-auth): Efficiently manage documents and user roles within R2R.
- [**🔭 Observability**](https://r2r-docs.sciphi.ai/self-hosting/observability): Observe and analyze your RAG engine performance.
- [**🧩 Configuration**](https://r2r-docs.sciphi.ai/self-hosting/configuration/overview): Setup your application using intuitive configuration files.
- [**🖥️ Dashboard**](https://github.com/SciPhi-AI/R2R-Application): An open-source React+Next.js admin dashboard to interact with R2R via GUI.


## Getting Started

### [SciPhi Cloud](https://app.sciphi.ai)

Access R2R through a deployment managed by the SciPhi team, which includes a generous free-tier. No credit card required.

## Self Hosting

Install R2R:

```bash
# Install the R2R package
pip install r2r

# Set necessary environment variables
export OPENAI_API_KEY=sk-...

# Run the server and database
r2r serve --docker --full
```

The command above will install the `full` installation which includes Hatchet for orchestration and Unstructured.io for parsing.


## Resources and Cookbooks

- [Quickstart](https://r2r-docs.sciphi.ai/documentation/quickstart): A quick introduction to R2R's core features
- [Self Hosting Installation](https://r2r-docs.sciphi.ai/self-hosting/installation/overview): Self hosted installation of R2R
- [API & SDKs](https://r2r-docs.sciphi.ai/api-and-sdks/introduction): API reference and Python/JS SDKs for interacting with R2R

- Advanced Retrieval
  - [RAG Agent](https://r2r-docs.sciphi.ai/documentation/agent): R2R's powerful RAG agent
  - [Hybrid Search](https://r2r-docs.sciphi.ai/documentation/hybrid-search): Introduction to hybrid search
  - [Advanced RAG](https://r2r-docs.sciphi.ai/documentation/advanced-rag): Advanced RAG features

### Cookbooks

- [Ingestion](https://r2r-docs.sciphi.ai/cookbooks/ingestion): Learn how to ingest, update, and delete documents with R2R
- [Knowledge Graphs](https://r2r-docs.sciphi.ai/cookbooks/graphs): Building and managing graphs through collections
- [Orchestration](https://r2r-docs.sciphi.ai/cookbooks/orchestration): Learn how orchestration is handled inside R2R
- [Maintenance & Scaling](https://r2r-docs.sciphi.ai/cookbooks/maintenance): Learn how to maintain and scale your R2R system
- [Web Development](https://r2r-docs.sciphi.ai/cookbooks/web-dev): Learn how to build webapps powered by RAG using R2R


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
