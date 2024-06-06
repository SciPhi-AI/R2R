<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

<img src="./docs/pages/r2r.png" alt="Sciphi Framework">
<h3 align="center">
Build, deploy, observe, and optimize your RAG system.
</h3>

# About

R2R, short for RAG to Riches, provides the fastest and most featureful way for developers to deliver high-quality Retrieval-Augmented Generation (RAG) to end users. The framework ships with a REST API powered by Postgres and pgvector - it includes user-level and document-level management as well as advanced RAG features.

## Why?

R2R was conceived to help developers bridge the gap between local LLM experimentation and serving a scalable, production-ready application. Built with document management, observability and customization in mind, R2R provides adequate performance and features for most RAG use cases.

## Key Features
- **🔧 Build**: Effortlessly create and manage observable, high-performance RAG pipelines with our robust framework. Including multimodal RAG, hybrid search, and latest methods such as HyDE.
- **🚀 Deploy**: Launch production-ready asynchronous RAG pipelines with seamless streaming capabilities. Begin serving users immediately with built-in user and document management features.
- **🧩 Customize**: Easily tailor your pipeline using intuitive configuration files to meet your specific needs.
- **🔌 Extend**: Enhance and extend your pipeline with custom code integrations to add new functionalities.
- **🤖 OSS**: Leverage a framework developed by the open-source community, ensuring flexibility, scalability, and ease of deployment.

## Table of Contents
1. [Quick Install](#quick-install)
2. [Links](#links)
3. [R2R Demo](#r2r-demo)
4. [R2R Server-Client Demo](#r2r-server-client-demo)
5. [Core Abstractions](#core-abstractions)
6. [Summary](#summary)


# Quick Install:

```bash
# use the `'r2r[all]'` to download all required deps
pip install r2r

# setup env 
export OPENAI_API_KEY=sk-...
```

# Serving R2R RAG backend

## With local installation

```bash
python -m r2r.examples.servers.configurable_pipeline --host 0.0.0.0 --port 8000
```
## With Docker

```bash
docker run -d --name r2r -p 8000:8000 r2r:latest
```

## Links

[Join the Discord server](https://discord.gg/p6KqD2kjtB)

[R2R Docs Quickstart](https://r2r-docs.sciphi.ai/getting-started/quick-install)

[SciPhi Cloud Docs](https://docs.sciphi.ai/)

# R2R Demo

The R2R demo offers a step-by-step guide on running the default R2R Retrieval-Augmented Generation (RAG) pipeline. The demo ingests a list of provided provided documents and demonstrates search, RAG, and advanced functionality. The script at `r2r/examples/demo.py`, which powers the demo, can be configured and extended with sufficient developer familiarity.

## Ingest Demo Files

To comprehensively demonstrate the RAG functionalities of the R2R framework, we must start by ingesting a realistic set of documents. Running the command below will parse, chunk, embed, and store a preset list of files. The included file types cover HTML, PDF, PNG, and TXT examples:

```bash
python -m r2r.examples.demo ingest_as_files
```

**Demo Output:**

```plaintext
...
r2r.pipes.parsing_pipe - INFO - Parsed document with metadata={'title': 'pg_essay_1.html', 'user_id': '063edaf8-3e63-4cb9-a4d6-a855f36376c3'} and id=4a4fb848-fc03-5487-a7e5-33c9fdfb73cc in t=0.00 seconds. - 2024-05-21 08:39:59,003
r2r.pipes.parsing_pipe - INFO - Parsed document with metadata={'title': 'lyft_2021.pdf', 'user_id': '063edaf8-3e63-4cb9-a4d6-a855f36376c3'} and id=c5abc0b7-b9e5-54d9-b3d3-fdb14af4d065 in t=3.47 seconds. - 2024-05-21 08:40:02,477
r2r.pipes.parsing_pipe - INFO - Parsed document with metadata={'title': 'screen_shot.png', 'user_id': '063edaf8-3e63-4cb9-a4d6-a855f36376c3', 'image_type': 'png'} and id=74f1506a-9a37-59d7-b288-5ef3683dca8f in t=18.37 seconds. - 2024-05-21 08:40:32,310
...
Time taken to ingest files: 28.49 seconds
```

### Confirm User Data

To verify the successful ingestion of the demo documents, you can fetch the metadata for the uploaded documents associated with the default demo user ID:

```bash
python -m r2r.examples.demo get_user_documents_metadata --user_id="063edaf8-3e63-4cb9-a4d6-a855f36376c3"
```

**Demo Output:**

```plaintext
...
Time taken to get user document data: 0.21 seconds
{'results': 
   [
      {
         'document_id': '327f6110-edd1-5fe3-b6b3-49b55f1cbc28',
         'title': 'pg_essay_3.html'
      }, 
      {
         'document_id': '946859f0-da5c-5db7-9b5c-c586be76d709', 
         'title': 'pg_essay_5.html'
      }, 
      {
         'document_id': '64c1c913-be06-548f-acbc-3618b00d3616', 
         'title': 'lyft_2021.pdf'
      },
      ...
   ]
}
```

## Search Demo Documents

Documents are stored by default in a local vector database. The vector database provider and settings can be specified via an input `config.json`. To perform a search query on the ingested user documents, use the following command:

```bash
python -m r2r.examples.demo search --query="Who was Aristotle?"
```

**Demo Output:**

```plaintext
...
Time taken to search: 0.39 seconds
{
   'id': UUID('93c44e73-8e95-50c2-84af-6a42f070b552'), 
   'score': 0.7739712385010018, 
   'metadata': 
   {
      'document_id': '15255e98-e245-5b58-a57f-6c51babf72dd', 
      'extraction_id': '5c61f9b9-b468-5fd7-8eb1-5d797a15c484', 
      'text': 'Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics,

 psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.', 
      'title': 'aristotle.txt',
      'user_id': '063edaf8-3e63-4cb9-a4d6-a855f36376c3', 
      'query': 'Who was Aristotle?'
   }
}
...
```

## RAG Demo

### Completion Response

To generate a response for a query using RAG, execute the following command:

```bash
python -m r2r.examples.demo rag --query="What was Uber's profit in 2020?"
```

**Demo Output:**

```plaintext
...
Time taken to run RAG: 2.29 seconds
{'results': 
   [
      ChatCompletion(
         id='chatcmpl-9RCB5xUbDuI1f0vPw3RUO7BWQImBN', 
         choices=[
            Choice(
               finish_reason='stop', 
               index=0, 
               logprobs=None, 
               message=ChatCompletionMessage(
                  content="Uber's profit in 2020 was a net loss of $6,768 million [10].", 
                  role='assistant', 
                  function_call=None, 
                  tool_calls=None
                  )
               )
            ], 
         created=1716268695, 
         model='gpt-3.5-turbo-0125', 
         object='chat.completion', 
         system_fingerprint=None, 
         usage=CompletionUsage(
            completion_tokens=20, 
            prompt_tokens=1470, 
            total_tokens=1490
            )
         )
   ]
}
```

### Streaming Response

For streaming results from a RAG query, use the following command:

```bash
python -m r2r.examples.demo rag --query="What was Lyft's profit in 2020?" --streaming=true
```

**Demo Output:**

```plaintext
r2r.main.r2r_config - INFO - Loading configuration from <YOUR_WORKDIR>/config.json - 2024-05-20 22:27:31,890
...
<search>["{\"id\":\"808c47c5-ebef-504a-a230-aa9ddcfbd87 .... </search>
<completion>Lyft reported a net loss of $1,752,857,000 in 2020 according to [2]. Therefore, Lyft did not make a profit in 2020.</completion>                                                      
Time taken to stream RAG response: 2.79 seconds
```

## Document Management Demo

### Update Document 

To update document(s) we may use the `update_as_files` or `update_as_documents` endpoints. Running the demo with `update_as_files` overwrites the data associated with 'aristotle.txt' with new data corresponding to 'aristotle_v2.txt' and increments the file version.

```bash
python -m r2r.examples.demo update_as_files
```

### Document Deletion

To delete a document by its ID, or any other metadata field, use the delete command. For example, to delete all chunks corresponding to the uploaded file `aristotle.txt`, we can call delete on the metadata field `document_id` with the value `15255e98-e245-5b58-a57f-6c51babf72dd`:

```bash
python -m r2r.examples.demo delete --keys="['document_id']" --values="['c9bdbac7-0ea3-5c9e-b590-018bd09b127b']"
```

### User Deletion

To delete all documents associated with a given user, run the delete command on the `user_id`:

```bash
run the following command with care, as it will erase all ingested user data
python -m r2r.examples.demo delete --keys="['user_id']" --values="['063edaf8-3e63-4cb9-a4d6-a855f36376c3']"
```

## R2R Server-Client Demo

This section extends the previous demo by showing how to set up and use the R2R framework with a server-client architecture. The R2R server can be stood up to handle requests, while the client can communicate with the server to perform various operations.

### Launch the Server

Use the following command to start the server:

```bash
python -m r2r.examples.demo serve
```

This command starts the R2R server on the default host `0.0.0.0` and port `8000`.

### Example Commands

1. **Ingest Documents as Files**:
   ```bash
   python -m r2r.examples.demo ingest_as_files --client_server_mode
   ```
   This command will send the ingestion request to the server running at `http://localhost:8000`.

2. **Perform a Search**:
   ```bash
   python -m r2r.examples.demo search --query="Who was Aristotle?" --client_server_mode
   ```
   This command sends the search query to the server and retrieves the results.

3. **Run a RAG Completion**:
   ```bash
   python -m r2r.examples.demo rag --query="What was Uber's profit in 2020?" --client_server_mode
   ```
   This command sends the RAG query to the server and retrieves the generated response.

4. **Run a RAG Stream**:
   ```bash
   python -m r2r.examples.demo rag --query="What was Lyft's profit in 2020?" --streaming=true --client_server_mode
   ```
   This command streams the RAG query results from the server.

### Server-Client Summary

By using the server-client model, you can extend the basic R2R demo to support more scalable and modular deployments. The server handles requests and performs heavy computations, while clients can communicate with the server to perform ingestion, search, RAG, and other operations, as shown in the examples above. For detailed setup and basic functionality, refer back to the [R2R Demo](#r2r-demo).


# Core Abstractions

The framework revolves around three core abstractions: Providers, Pipes, and Pipelines.

## Providers

Providers supply the necessary resources and capabilities to the pipes and pipelines. Key provider types include:

- **Vector Database Provider**: Manages the storage and retrieval of vector embeddings. Examples include PGVector, and SQLite.
- **Embedding Provider**: Converts text into vector embeddings. Supported providers include OpenAI, SentenceTransformers, and DummyEmbeddingProvider.
- **LLM Provider**: Interfaces with large language models for text generation. Supported providers include OpenAI, and LiteLLM.
- **Prompt Provider**: Manages prompts for various tasks.
- **Eval Provider**: Evaluates the quality of generated responses.

## Pipes

Pipes represent individual steps in the data processing workflow. Each pipe performs a specific task, such as parsing, embedding, searching, or generating text. Pipes are designed to be composable and reusable within different pipelines.

- **Parsing Pipe**: Extracts and structures data from various formats.
- **Embedding Pipe**: Generates embeddings from text and stores them in a vector database.
- **Vector Storage Pipe**: Handles the storage of embeddings in a vector database.
- **Search Pipe**: Performs vector-based searches.
- **RAG Pipe**: Integrates search results with language generation to produce responses.
- **Streaming RAG Pipe**: Extends RAG functionality to support streaming responses.
- **Eval Pipe**: Evaluates the quality of generated responses.

## Pipelines

Pipelines are composed of multiple pipes arranged in a sequence. They manage the flow of data through the pipes, ensuring that each step is executed in the correct order. R2R supports several types of pipelines:

- **Ingestion Pipeline**: Prepares and ingests documents, converting them into embeddings.
- **Embedding Pipeline**: Manages the transformation of text into vector embeddings.
- **RAG Pipeline**: Combines search and language generation to produce detailed responses.
- **Eval Pipeline**: Evaluates the quality of generated responses using LLM-powered evaluations.

# Summary

R2R (RAG to Riches) is a comprehensive framework designed to streamline the development, deployment, and optimization of Retrieval-Augmented Generation (RAG) systems. With its robust core abstractions—Providers, Pipes, and Pipelines—R2R offers a modular and flexible approach to building high-quality RAG pipelines.
