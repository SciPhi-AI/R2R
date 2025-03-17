![R2R Logo](https://github.com/user-attachments/assets/16d32b31-4c7d-4e84-be19-24574b33527b)

<h3 align="center">
The most advanced AI retrieval system.

Agentic Retrieval-Augmented Generation (RAG) with a RESTful API.
</h3>

<div align="center">
   <div>
      <h3>
         <a href="https://app.sciphi.ai"><strong>Sign up</strong></a> ·
         <a href="https://r2r-docs.sciphi.ai/self-hosting/installation/overview"><strong>Self Host</strong></a>
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
  </p>
</div>

# About
R2R (Reason to Retrieve) is an advanced AI retrieval system supporting Retrieval-Augmented Generation (RAG) with production-ready features. Built around a RESTful API, R2R offers multimodal content ingestion, hybrid search, knowledge graphs, and comprehensive document management.

R2R also includes a **Deep Research API**, a multi-step reasoning system that fetches relevant data from your knowledgebase and/or the internet to deliver richer, context-aware answers for complex queries.


## Getting Started

### Cloud Option: [SciPhi Cloud](https://app.sciphi.ai)
Access R2R through SciPhi's managed deployment with a generous free tier. No credit card required.

### Self-Hosting Option

```bash
# Quick install and run in light mode
pip install r2r
export OPENAI_API_KEY=sk-...
python -m r2r.serve

# Or run in full mode with Docker
# git clone git@github.com:SciPhi-AI/R2R.git && cd R2R
# export R2R_CONFIG_NAME=full OPENAI_API_KEY=sk-...
# docker compose -f compose.full.yaml --profile postgres up -d
```

For detailed self-hosting instructions, see the [self-hosting docs](https://r2r-docs.sciphi.ai/self-hosting/installation/overview).

## Demo
https://github.com/user-attachments/assets/173f7a1f-7c0b-4055-b667-e2cdcf70128b

## Using the API

### 1. Install SDK & Setup

```bash
# Install SDK
pip install r2r  # Python
# or
npm i r2r-js    # JavaScript

# Setup API key
export R2R_API_KEY=pk_..sk_...  # Get from SciPhi Cloud dashboard
```

### 2. Client Initialization

```python
from r2r import R2RClient
client = R2RClient()  # Use base_url=... for self-hosted
```

```javascript
const { r2rClient } = require('r2r-js');
const client = new r2rClient();  // Use baseURL=... for self-hosted
```

### 3. Document Operations

```python
# Ingest sample or your own document
client.documents.create_sample(hi_res=True)
# client.documents.create(file_path="/path/to/file")

# List documents
client.documents.list()
```

### 4. Search & RAG

```python
# Basic search
results = client.retrieval.search(query="What is DeepSeek R1?")

# RAG with citations
response = client.retrieval.rag(query="What is DeepSeek R1?")

# Agentic reasoning with RAG
response = client.retrieval.agent(
  message={"role":"user", "content": "What does deepseek r1 imply? Think about market, societal implications, and more."},
  rag_generation_config={
    "model"="anthropic/claude-3-7-sonnet-20250219",
    "extended_thinking": True,
    "thinking_budget": 4096,
    "temperature": 1,
    "top_p": None,
    "max_tokens_to_sample": 16000,
  },
  mode="research" # for Deep Research style output
)
```

## Key Features

- **📁 Multimodal Ingestion**: Parse `.txt`, `.pdf`, `.json`, `.png`, `.mp3`, and more
- **🔍 Hybrid Search**: Semantic + keyword search with reciprocal rank fusion
- **🔗 Knowledge Graphs**: Automatic entity & relationship extraction
- **🤖 Agentic RAG**: Reasoning agent integrated with retrieval
- **🔐 User & Access Management**: Complete authentication & collection system

## Community & Contributing

- [Join our Discord](https://discord.gg/p6KqD2kjtB) for support and discussion
- Submit [feature requests](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=feature_request.md&title=) or [bug reports](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=bug_report.md&title=)
- Open PRs for new features, improvements, or documentation

### Our Contributors
<a href="https://github.com/SciPhi-AI/R2R/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SciPhi-AI/R2R" />
</a>
