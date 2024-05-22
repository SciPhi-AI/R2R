<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

<img src="./docs/pages/r2r.png" alt="Sciphi Framework">
<h3 align="center">
Build, deploy, and optimize your RAG system.
</h3>

## About

R2R, short for RAG to Riches, provides the fastest and most efficient way to deliver high-quality Retrieval-Augmented Generation (RAG) to end users. The framework is built around customizable pipelines and a feature-rich FastAPI implementation.

## Why?

R2R was conceived to bridge the gap between local LLM experimentation and scalable production solutions. It is built with observability and customization in mind, ensuring that users can seamlessly transition from development to deployment.

### Key Features
- **🔧 Build**: Use the framework to build arbitrary asynchronous pipelines.
- **🚀 Deploy**: Instantly launch production-ready asynchronous RAG pipelines with streaming capabilities.
- **🧩 Customize**: Tailor your pipeline with intuitive configuration files.
- **🔌 Extend**: Enhance your pipeline with custom code integrations.
- **🤖 OSS**: Benefit from a framework developed by the open-source community, designed to simplify RAG deployment.


# Table of Contents
1. [Demo(s)](#demos)
2. [Links](#links)
3. [Quick Install](#quick-install)
4. [Docker](#docker)
5. [R2R Demo](#r2r-demo)
6. [R2R Server-Client Demo](#r2r-server-client-demo)
7. [Core Abstractions](#core-abstractions)

## Demo(s)

Using the cloud application to deploy the pre-built basic pipeline:

<iframe src="https://www.loom.com/embed/e3b934b554484787b005702ced650ac9" frameborder="0" webkitallowfullscreen mozallowfullscreen allowfullscreen style={{ width: '100%', height: '400px', border: 'none' }}></iframe>

Note - the example above uses [SciPhi Cloud](https://sciphi.ai) to pair with the R2R framework for deployment and observability. SciPhi is working to launch a self-hosted version of their cloud platform as R2R matures.

## Links

[Join the Discord server](https://discord.gg/p6KqD2kjtB)

[R2R Docs Quickstart](https://r2r-docs.sciphi.ai/getting-started/quick-install)

[SciPhi Cloud Docs](https://docs.sciphi.ai/)

[Local RAG Tutorial](https://r2r-docs.sciphi.ai/tutorials/local_rag)

## Quick Install:

```bash
# use the `'r2r[all]'` to download all required deps
pip install r2r

# setup env 
export OPENAI_API_KEY=sk-...
```

## Docker:

```bash
docker pull emrgntcmplxty/r2r:latest

# Choose from CONFIG_OPTION in {`default`, `local_ollama`}
# For cloud deployment, select `default` and pass `--env-file .env`
# For local deployment, select `local_ollama`
docker run -d --name r2r_container -p 8000:8000 -e CONFIG_OPTION=local_ollama  emrgntcmplxty/r2r:latest
```

## R2R Demo

This example demonstrates how to set up and use the R2R framework to run the default R2R Retrieval-Augmented Generation (RAG) pipeline. The demo utilizes a locally defined `config.json` (which defaults to the config.json included with R2R) to build ingestion and RAG pipelines, along with several demonstration methods.

The sections below cover R2R setup, basic functionality, document management, and some advanced features.

### Setup

To get started with the R2R framework, follow these steps to install dependencies, set up your environment, and ingest sample documents for the demo.

#### Step 0: Quick Install

First, you'll need to install the necessary dependencies and set up your environment.

```bash
# use the `'r2r[all]'` to download all possible required deps
pip install r2r

# OpenAI is the default provider and requires an API key
export OPENAI_API_KEY="sk-..."
```

#### Step 1: Ingest Demo Files

To comprehensively demonstrate the RAG functionalities of the R2R framework, we must start by ingesting a realistic set of documents. Running the command below will parse, chunk, embed, and store a preset list of files. The included file types cover HTML, PDF, PNG, and TXT examples:

```bash
poetry run python -m r2r.examples.demo ingest_as_files
```

**Note**

Each ingested document is given its own `document_id`, which is derived uniquely from the input file path. As the document is parsed, chunked, and embedded, this association is maintained to allow for frictionless vector database management. Additionally, a default `user_id` is included throughout the demo to illustrate how user document management can be handled similarly.

#### Step 2: Confirm User Data

To verify the documents associated with the default user ID, you can fetch the metadata for the uploaded documents:

```bash
poetry run python -m r2r.examples.demo get_user_document_data --user_id="063edaf8-3e63-4cb9-a4d6-a855f36376c3"
```

**Example Output:**

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

### Basic Functionality

The basic functionality of the R2R framework allows you to search ingested documents and generate responses using Retrieval-Augmented Generation (RAG). These steps will guide you through performing a search query, generating a RAG response, and streaming RAG results.

#### Step 3: Run a Demo Search

Documents are stored by default in a local vector database. The vector database provider and settings can be specified via an input `config.json`. To perform a search query on the ingested user documents, use the following command:

```bash
poetry run python -m r2r.examples.demo search --query="Who was Aristotle?"
```

**Example Output:**

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
      'text': 'Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began

 the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.', 
      'title': 'aristotle.txt',
      'user_id': '063edaf8-3e63-4cb9-a4d6-a855f36376c3', 
      'query': 'Who was Aristotle?'
   }
}
...
```

#### Step 4: Run a Demo RAG Completion

To generate a response for a query using RAG, execute the following command:

```bash
poetry run python -m r2r.examples.demo rag --query="What was Ubers profit in 2020?"
```

**Example Output:**

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

#### Step 5: Run a Demo RAG Stream

For streaming results from a RAG query, use the following command:

```bash
poetry run python -m r2r.examples.demo rag --query="What was Lyfts profit in 2020?" --streaming=True
```

**Example Output:**

```plaintext
r2r.main.r2r_config - INFO - Loading configuration from <YOUR_WORKDIR>/config.json - 2024-05-20 22:27:31,890
...
<search>["{\"id\":\"808c47c5-ebef-504a-a230-aa9ddcfbd87 .... </search>
<completion>Lyft reported a net loss of $1,752,857,000 in 2020 according to [2]. Therefore, Lyft did not make a profit in 2020.</completion>                                                      
Time taken to stream RAG response: 2.79 seconds
```

### Document Management

Effective document management is crucial for maintaining a robust and efficient RAG system. This section guides you through various operations related to document management, including deleting documents and managing user-specific data. These steps will help ensure your document database remains organized and up-to-date.

#### Step 6: Delete a Specified Document

To delete a document by its ID, or any other metadata field, use the delete command. For example, to delete all chunks corresponding to the uploaded file `aristotle.txt`, we can call delete on the associated document ID with the value `15255e98-e245-5b58-a57f-6c51babf72dd`:

```bash
poetry run python -m r2r.examples.demo delete --key=document_id --value=15255e98-e245-5b58-a57f-6c51babf72dd
```

After deleting a document, you can run a search command to verify its removal:

```bash
poetry run python -m r2r.examples.demo search --query="Who was Aristotle?"
```


**Note**

The quality of search results has dramatically decreased now that the Aristotle-specific document has been fully erased. This highlights the importance of the ingested data quality on the RAG results.

#### Step 7: Delete a Specified User's Documents

To delete all documents associated with a given user, run the delete command on the `user_id`.

```bash
run the following command with care, as it will erase all ingested user data
poetry run python -m r2r.examples.demo delete --key=user_id --value=063edaf8-3e63-4cb9-a4d6-a855f36376c3
```

Afterwards, we may confirm complete user documentation through the `get_user_document_data` functionality.

**Example Output:**

```bash
...
Time taken to get user document data: 0.00 seconds
{'results': []}
```

## R2R Server-Client Demo

This document extends the [R2R Demo](#r2r-demo) by demonstrating how to set up and use the R2R framework with a server-client architecture. The R2R server can be stood up to handle requests, while the client can communicate with the server to perform various operations. The server API can be viewed here.

### Overview

The R2R framework provides a way to run a Retrieval-Augmented Generation (RAG) pipeline using a server-client model. This allows for a centralized server to handle requests from multiple clients, enabling more scalable and modular deployments.

### Setting Up the Server

To set up the R2R server, follow these steps:

1. **Quick Install**:
   Ensure you have all necessary dependencies installed as described in the [R2R Demo](#r2r-demo#setup).

2. **Start the R2R Server**:
   Use the following command to start the server:
   ```bash
   poetry run python -m r2r.examples.demo serve
   ```
   This command starts the R2R server on the default host `0.0.0.0` and port `8000`.

### Using the Client

The R2R framework includes a client that can communicate with the R2R server to perform various operations. You can use any of the demo commands with the `--base_url` parameter to specify the server's address.

#### Example Commands

1. **Ingest Documents as Files**:
   ```bash
   poetry run python -m r2r.examples.demo ingest_as_files --base_url=http://localhost:8000
   ```
   This command will send the ingestion request to the server running at `http://localhost:8000`.

2. **Perform a Search**:
   ```bash
   poetry run python -m r2r.examples.demo search --query="Who was Aristotle?" --base_url=http://localhost:8000
   ```
   This command sends the search query to the server and retrieves the results.

3. **Run a RAG Completion**:
   ```bash
   poetry run python -m r2r.examples.demo rag --query="What was Uber's profit in 2020?" --base_url=http://localhost:8000
   ```
   This command sends the RAG query to the server and retrieves the generated response.

4. **Run a RAG Stream**:
   ```bash
   poetry run python -m r2r.examples.demo rag --query="What was

 Lyft's profit in 2020?" --streaming=True --base_url=http://localhost:8000
   ```
   This command streams the RAG query results from the server.

## Core Abstractions

The framework primarily revolves around three core abstractions:

- The **Ingestion Pipeline**: Facilitates the preparation of embeddable 'Documents' from various data formats (json, txt, pdf, html, etc.). The abstraction can be found in [`ingestion.py`](r2r/core/pipelines/ingestion.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/deep-dive/ingestion).

- The **Embedding Pipeline**: Manages the transformation of text into stored vector embeddings, interacting with embedding and vector database providers through a series of steps (e.g., extract_text, transform_text, chunk_text, embed_chunks, etc.). The abstraction can be found in [`embedding.py`](r2r/core/pipelines/embedding.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/deep-dive/embedding).

- The **RAG Pipeline**: Works similarly to the embedding pipeline but incorporates an LLM provider to produce text completions. The abstraction can be found in [`rag.py`](r2r/core/pipelines/rag.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/deep-dive/rag).

- The **Eval Pipeline**: Samples some subset of rag_completion calls for evaluation. Currently [DeepEval](https://github.com/confident-ai/deepeval) and [Parea](https://github.com/parea-ai/parea-sdk-py) are supported. The abstraction can be found in [`eval.py`](r2r/core/pipelines/eval.py) and relevant documentation is available [here](https://r2r-docs.sciphi.ai/deep-dive/eval).

Each pipeline incorporates a logging database for operation tracking and observability.