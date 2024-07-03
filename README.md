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

<details>
<summary><b>Installing with Pip</b>&nbsp;🐍 </summary>

```bash
pip install r2r

# setup env, can freely replace `demo_vecs`
export OPENAI_API_KEY=sk-...
export POSTGRES_USER=YOUR_POSTGRES_USER
export POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD
export POSTGRES_HOST=YOUR_POSTGRES_HOST
export POSTGRES_PORT=YOUR_POSTGRES_PORT
export POSTGRES_DBNAME=YOUR_POSTGRES_DBNAME
export POSTGRES_VECS_COLLECTION=demo_vecs
```
</details>

<details open>
<summary><b>Installing with Docker</b>&nbsp;🐳</summary>
Docker allows users to get started with R2R seamlessly—providing R2R, the R2R Dashboard, and a pgvector database all in one place.

First, clone the R2R repository:
```bash
git clone https://github.com/SciPhi-AI/R2R.git
cd R2R
```

Then, run the following command to start all containers:

For hosted LLMs (e.g., OpenAI):
```bash
# Be sure to set an OpenAI API key
export OPENAI_API_KEY=sk-...
docker-compose up -d
```

For local LLMs (e.g., Ollama):
```bash
OLLAMA_API_BASE=http://host.docker.internal:11434 CONFIG_OPTION=local_ollama docker-compose up -d
```

Note: You can override the pgvector collection by setting an environment variable when calling `docker-compose`. This is useful when switching between different sized embeddings:
```bash
POSTGRES_VECS_COLLECTION=new_vecs docker-compose up -d
```

The R2R client must still be installed when using Docker. Install it with `pip install r2r`.
</details>

# Updates
Star R2R on GitHub by clicking "Star" in the upper right hand corner of the page to be instantly notified of new releases.


# R2R Quickstart

## Start the R2R server
<details open>
<summary><b>Serving the R2R CLI</b>&nbsp;✈️ </summary>

```bash
r2r serve --port=8000
```

```plaintext Terminal Output
2024-06-26 16:54:46,998 - INFO - r2r.core.providers.vector_db_provider - Initializing VectorDBProvider with config extra_fields={} provider='pgvector' collection_name='demo_vecs'.
2024-06-26 16:54:48,054 - INFO - r2r.core.providers.embedding_provider - Initializing EmbeddingProvider with config extra_fields={'text_splitter': {'type': 'recursive_character', 'chunk_size': 512, 'chunk_overlap': 20}} provider='openai' base_model='text-embedding-3-small' base_dimension=512 rerank_model=None rerank_dimension=None rerank_transformer_type=None batch_size=128.
2024-06-26 16:54:48,639 - INFO - r2r.core.providers.llm_provider - Initializing LLM provider with config: extra_fields={} provider='litellm'
```

</details>

<details>
<summary><b>Serving with Docker</b>&nbsp;🐳</summary>

Successfully completing the installation steps above results in an R2R application being served over port `8000`.

</details>

## Ingest a file

```bash
r2r ingest
# can be called with additional argument,
# e.g. `r2r ingest /path/to/your_file_1 /path/to/your_file_2 ...`
```

```plaintext
{'results': {'processed_documents': ["File '.../aristotle.txt' processed successfully."], 'skipped_documents': []}}
```


## Perform a search


```bash
r2r search --query="who was aristotle?" --do-hybrid-search
```

```plaintext
{'results': {'vector_search_results': [
    {
        'id': '7ed3a01c-88dc-5a58-a68b-6e5d9f292df2',
        'score': 0.780314067545999,
        'metadata': {
            'text': 'Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.',
            'title': 'aristotle.txt',
            'version': 'v0',
            'chunk_order': 0,
            'document_id': 'c9bdbac7-0ea3-5c9e-b590-018bd09b127b',
            'extraction_id': '472d6921-b4cd-5514-bf62-90b05c9102cb',
            ...
```

## Perform RAG


```bash
r2r rag --query="who was aristotle?" --do-hybrid-search
```

```plaintext

Search Results:
{'vector_search_results': [
    {'id': '7ed3a01c-88dc-5a58-a68b-6e5d9f292df2',
    'score': 0.7802911996841491,
    'metadata': {'text': 'Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic schoo
    ...
Completion:
{'results': [
    {
        'id': 'chatcmpl-9eXL6sKWlUkP3f6QBnXvEiKkWKBK4',
        'choices': [
            {
                'finish_reason': 'stop',
                'index': 0,
                'logprobs': None,
                'message': {
                    'content': "Aristotle (384–322 BC) was an Ancient Greek philosopher and polymath whose writings covered a broad range of subjects including the natural sciences,
                    ...
```



## Stream a RAG Response


```bash
r2r rag --query="who was aristotle?" --stream --do-hybrid-search
```

```plaintext
<search>"{\"id\":\"004ae2e3-c042-50f2-8c03-d4c282651fba\",\"score\":0.7803140675 ...</search>
<completion>Aristotle was an Ancient Greek philosopher and polymath who lived from 384 to 322 BC [1]. He was born in Stagira, Chalcidi....</completion>
```

# Hello r2r

Building with R2R is easy - see the `hello_r2r` example below:

```python

from r2r import Document, GenerationConfig, R2R

app = R2R() # You may pass a custom configuration to `R2R`

app.ingest_documents(
    [
        Document(
            type="txt",
            data="John is a person that works at Google.",
            metadata={},
        )
    ]
)

rag_results = app.rag(
    "Who is john", GenerationConfig(model="gpt-3.5-turbo", temperature=0.0)
)
print(f"Search Results:\n{rag_results.search_results}")
print(f"Completion:\n{rag_results.completion}")

# RAG Results:
# Search Results:
# AggregateSearchResult(vector_search_results=[VectorSearchResult(id=2d71e689-0a0e-5491-a50b-4ecb9494c832, score=0.6848798582029441, metadata={'text': 'John is a person that works at Google.', 'version': 'v0', 'chunk_order': 0, 'document_id': 'ed76b6ee-dd80-5172-9263-919d493b439a', 'extraction_id': '1ba494d7-cb2f-5f0e-9f64-76c31da11381', 'associatedQuery': 'Who is john'})], kg_search_results=None)
# Completion:
# ChatCompletion(id='chatcmpl-9g0HnjGjyWDLADe7E2EvLWa35cMkB', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content='John is a person that works at Google [1].', role='assistant', function_call=None, tool_calls=None))], created=1719797903, model='gpt-3.5-turbo-0125', object='chat.completion', service_tier=None, system_fingerprint=None, usage=CompletionUsage(completion_tokens=11, prompt_tokens=145, total_tokens=156))
```

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
