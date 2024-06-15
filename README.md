<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
</p>

<img src="./docs/pages/r2r.png" alt="Sciphi Framework">
<h3 align="center">
Build, deploy, observe, and optimize your RAG engine.
</h3>

# About

R2R (Rag to Riches) is the ultimate open-source framework for building and deploying high-quality Retrieval-Augmented Generation (RAG) systems. Designed to bridge the gap between local LLM experimentation and scalable, production-ready applications, R2R provides a comprehensive, feature-rich environment for developers.

For a more complete view of R2R, check out our [documentation](https://r2r-docs.sciphi.ai/).


## Key Features
- **📁 Multimodal Support**: Ingest files ranging from `.txt`, `.pdf`, `.json` to `.png`, `.mp3`, and more.
- **🔍 Hybrid Search**: Combine semantic and keyword search with reciprocal rank fusion for enhanced relevancy.
- **🔗 Graph RAG**: Automatically extract relationships and build knowledge graphs.
- **🗂️ App Management**: Efficiently manage documents and users with rich observability and analytics.
- **🌐 Client-Server**: RESTful API support out of the box.
- **🧩 Configurable**: Provision your application using intuitive configuration files.
- **🔌 Extensible**: Develop your application further with easy builder + factory pattern.
- **🖥️ Dashboard**: Use the [R2R Dashboard](https://github.com/SciPhi-AI/R2R-Dashboard), an open-source React+Next.js app for a user-friendly interaction with your pipelines.

## Table of Contents
1. [Quick Install](#quick-install)
2. [R2R Python SDK Demo](#r2r-python-sdk-demo)
3. [R2R Dashboard](#r2r-dashboard)
4. [Community and Support](#community-and-support)
5. [Contributing](#contributing)


# Quick Install:

<details open>
<summary><b>Installing with Pip</b>&nbsp;🐍 </summary>

```bash
# use the `'r2r[all]'` to download all required deps
pip install r2r

# setup env 
export OPENAI_API_KEY=sk-...
```
</details>

<details>
<summary><b>Installing with Docker</b>&nbsp;🐳</summary>

To run R2R using Docker, you can use the following commands:

```bash filename="bash" copy
docker pull emrgntcmplxty/r2r:latest
```

This will pull the latest R2R Docker image.

Be sure to set an OpenAI API key in your environment and then run the container with:

```bash filename="bash" copy
docker run -d \
  --name r2r \
  --add-host=host.docker.internal:host-gateway \
  -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  emrgntcmplxty/r2r:latest
```

This command starts the R2R container with the following options:

- `--name r2r`: Assigns the name "r2r" to the container.
- `--add-host=host.docker.internal:host-gateway`: Adds a host entry for the Docker host.
- `-p 8000:8000`: Maps port 8000 of the container to port 8000 of the host.
- `-e OPENAI_API_KEY=$OPENAI_API_KEY`: Pulls your OpenAI API key from your local enviornment for use in the container.
- `emrgntcmplxty/r2r:latest`: Specifies the Docker image to use.
</details>


# R2R Python SDK Demo

The following demo offers a step-by-step guide on running the default R2R Retrieval-Augmented Generation (RAG) pipeline using the Python SDK. The demo ingests a list of provided provided documents and demonstrates search, RAG, and advanced functionality. The script at `r2r/examples/quickstart.py`, which powers the demo, can be configured and extended with sufficient developer familiarity.

![ingest_as_files](https://github.com/SciPhi-AI/R2R/assets/34580718/b0780f26-8e90-4459-9537-e5871453d003)


<details open>
<summary> <b>Interacting with your Documents</b></summary>

1. **Ingesting Files**:
   To comprehensively demonstrate the RAG functionalities of the R2R framework, we must start by ingesting a realistic set of documents. Running the command below will parse, chunk, embed, and store a preset list of files. The included file types cover HTML, PDF, PNG, and TXT examples:

   ```bash
   python -m r2r.examples.quickstart ingest_as_files
   ```

   **Demo Output:**

   ```plaintext
   ...
   r2r.main.r2r_config - INFO - Loading configuration from <YOUR_WORKDIR>/config.json - 2024-05-20 22:08:48,025
   r2r.core.providers.llm_provider - INFO - Initializing LLM provider with config: extra_fields={} provider='litellm' - 2024-05-20 22:08:48,562
   r2r.core.providers.vector_db_provider - INFO - Initializing VectorDBProvider with config extra_fields={} provider='local' collection_name='demo_vecs'. - 2024-05-20 22:08:48,765
   r2r.providers.embeddings.openai.openai_base - INFO - Initializing `OpenAIEmbeddingProvider` to provide embeddings. - 2024-05-20 22:08:48,774
   ...
   r2r.pipes.parsing_pipe - INFO - Parsed document with metadata={'title': 'pg_essay_5.html', 'user_id': '063edaf8-3e63-4cb9-a4d6-a855f36376c3'} and id=ef66e5dd-2130-5fd5-9bdd-aa7eff59fda5 in t=0.00 seconds. - 2024-05-21 08:40:32,317
   r2r.pipes.embedding_pipe - INFO - Fragmented the input document ids into counts as shown: {UUID('4a4fb848-fc03-5487-a7e5-33c9fdfb73cc'): 31, UUID('c5abc0b7-b9e5-54d9-b3d3-fdb14af4d065'): 2094, UUID('f0c63aff-af59-50c9-81fc-2fe55004c771'): 17, UUID('c996e617-88a4-5c65-ab1e-948344b18d27'): 3108, UUID('1a9d4d3b-bbe9-53b9-8149-67806bdf60f2'): 18, UUID('c9bdbac7-0ea3-5c9e-b590-018bd09b127b'): 233, UUID('b722f1ec-b90e-5ed8-b7c8-c768e8b323cb'): 5, UUID('74f1506a-9a37-59d7-b288-5ef3683dca8f'): 10, UUID('ef66e5dd-2130-5fd5-9bdd-aa7eff59fda5'): 11} - 2024-06-04 13:34:40,885
   {'results': ["File 'aristotle.txt' processed successfully.", "File 'screen_shot.png' processed successfully.", "File 'pg_essay_1.html' processed successfully.", "File 'pg_essay_2.html' processed successfully.", "File 'pg_essay_3.html' processed successfully.", "File 'pg_essay_4.html' processed successfully.", "File 'pg_essay_5.html' processed successfully.", "File 'lyft_2021.pdf' processed successfully.", "File 'uber_2021.pdf' processed successfully.", "File sample.mp3 processed successfully.", "File sample2.mp3 processed successfully."]}
   ...
   ```
2. **Document Info**:
   To verify the successful ingestion of the demo documents, you can fetch the metadata for the uploaded documents associated with the default demo user ID:

   ```bash
   python -m r2r.examples.quickstart documents_info
   ```

   **Demo Output:**

   ```plaintext
   [
      DocumentInfo(
         document_id=UUID('c9bdbac7-0ea3-5c9e-b590-018bd09b127b'), 
         version='v0', 
         size_in_bytes=73353, 
         metadata={'title': 'aristotle.txt', 'user_id': '063edaf8-3e63-4cb9-a4d6-a855f36376c3'}, 
         title='aristotle.txt'
      ), 
      ... 
   ]
   ```


   ```bash
   python -m r2r.examples.quickstart users_stats
   ```


   ```plaintext
   [
      UserStats(
         user_id=UUID('063edaf8-3e63-4cb9-a4d6-a855f36376c3'), 
         num_files=9,
         total_size_in_bytes=4809510, 
         document_ids=[UUID('c9bdbac7-0ea3-5c9e-b590-018bd09b127b'), ...]
      ), 
   ]
   ```
</details>


<details>
<summary><b>Basic RAG Functionality</b></summary>

![search](https://github.com/SciPhi-AI/R2R/assets/34580718/6c21d8f8-7f4e-45b6-917a-39462b83d3ca)


1. **Search Documents**
   Documents are stored by default in a local vector database. The vector database provider and settings can be specified via an input `config.json`. To perform a search query on the ingested user documents, use the following command:

   ```bash
   python -m r2r.examples.quickstart search --query="Who was Aristotle?"
   ```

   **Demo Output:**

   ```plaintext
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
         'associatedQuery': 'Who was Aristotle?'
      }
   },
   ...
   ```

2. **Completion Response**:
   To generate a response for a query using RAG, execute the following command:

   ```bash
   python -m r2r.examples.quickstart rag --query="What was Uber's profit in 2020?"
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

3. **Streaming Response**:
   For streaming results from a RAG query, use the following command:

   ```bash
   python -m r2r.examples.quickstart rag --query="What was Lyft's profit in 2020?" --streaming=true
   ```

   **Demo Output:**

   ```plaintext
   r2r.main.r2r_config - INFO - Loading configuration from <YOUR_WORKDIR>/config.json - 2024-05-20 22:27:31,890
   ...
   <search>["{\"id\":\"808c47c5-ebef-504a-a230-aa9ddcfbd87 .... </search>
   <completion>Lyft reported a net loss of $1,752,857,000 in 2020 according to [2]. Therefore, Lyft did not make a profit in 2020.</completion>                                                      
   Time taken to stream RAG response: 2.79 seconds
   ```

</details>



<details>
<summary><b>Document Management</b></summary>

1. **Update Document**:
   To update document(s) we may use the `update_as_files` or `update_as_documents` endpoints. Running the demo with `update_as_files` overwrites the data associated with 'aristotle.txt' with new data corresponding to 'aristotle_v2.txt' and increments the file version.

   ```bash
   python -m r2r.examples.quickstart update_as_files
   ```

2. **Document Deletion**:
   To delete a document by its ID, or any other metadata field, use the delete command. For example, to delete all chunks corresponding to the uploaded file `aristotle.txt`, we can call delete on the metadata field `document_id` with the value `15255e98-e245-5b58-a57f-6c51babf72dd`:

   ```bash
   python -m r2r.examples.quickstart delete --keys="['document_id']" --values="['c9bdbac7-0ea3-5c9e-b590-018bd09b127b']"
   ```

3. **User Specific Document Deletion**:
   To delete all documents associated with a given user, run the delete command on the `user_id`:

   ```bash
   # run the following command with care, as it will erase all ingested user data for `063edaf8-3e63-4cb9-a4d6-a855f36376c3`
   python -m r2r.examples.quickstart delete --keys="['user_id']" --values="['063edaf8-3e63-4cb9-a4d6-a855f36376c3']"
   ```
</details>

<details>
   <summary> <b>R2R in Client-Server Mode</b></summary>
   The R2R framework extends to support interactions with a client-server architecture. The R2R server can be stood up to handle requests, while the client can communicate with the server to perform various operations.

   ### Launch the Server

   Use the following command to start the server:

   ```bash
   python -m r2r.examples.quickstart serve
   ```

   This command starts the R2R server on the default host `0.0.0.0` and port `8000`.

   ### Example Commands

   1. **Ingest Documents as Files**:
      ```bash
      python -m r2r.examples.quickstart ingest_as_files --client_server_mode
      ```
      This command will send the ingestion request to the server running at `http://localhost:8000`.

   2. **Perform a Search**:
      ```bash
      python -m r2r.examples.quickstart search --query="Who was Aristotle?" --client_server_mode
      ```
      This command sends the search query to the server and retrieves the results.

   3. **Run a RAG Completion**:
      ```bash
      python -m r2r.examples.quickstart rag --query="What was Uber's profit in 2020?" --client_server_mode
      ```
      This command sends the RAG query to the server and retrieves the generated response.

   4. **Run a RAG Stream**:
      ```bash
      python -m r2r.examples.quickstart rag --query="What was Lyft's profit in 2020?" --streaming=true --client_server_mode
      ```
      This command streams the RAG query results from the server.

   ### Client-Server Summary

   By using the Client-Server model, you can extend the basic R2R quickstart to support more scalable and modular deployments. The server handles requests and performs heavy computations, while clients can communicate with the server to perform ingestion, search, RAG, and other operations, as shown in the examples above. For detailed setup and basic functionality, refer back to the [R2R quickstart](#quickstart).
</details>

# R2R Dashboard

Developers can interact with R2R in several ways, including through our [open-source React+Next.js dashboard](https://github.com/SciPhi-AI/R2R-Dashboard). The dashboard is designed to give R2R developers an easy way to interface with their pipelines, reducing development and iteration time. Checkout the [Dashboard Cookbook](https://r2r-docs.sciphi.ai/cookbooks/dashboard) to get started!

# Community and Support

We're here to help! Feel free to reach out for support on any of these channels:

- [Discord](https://discord.gg/p6KqD2kjtB) \(Chat live with maintainers and community members\)
- [Github Issues](https://github.com/SciPhi-AI/R2R/issues) \(Bug reports and feature requests\)

There are a number of helpful tutorials and cookbooks that can be found in the [R2R Docs](https://r2r-docs.sciphi.ai/):
- [R2R Quickstart](https://r2r-docs.sciphi.ai/getting-started/quickstart): A basic demo script designed to get you started with an R2R RAG application. 
- [R2R Client-Server](https://r2r-docs.sciphi.ai/cookbooks/client-server): An extension of the basic `R2R Quickstart` with client-server interactions.
- [Local RAG](https://r2r-docs.sciphi.ai/cookbooks/local-rag): A quick cookbook demonstration of how to run R2R with local LLMs.
- [Hybrid Search](https://r2r-docs.sciphi.ai/cookbooks/hybrid-search): A brief introduction to running hybrid search with R2R.
- [Reranking](https://r2r-docs.sciphi.ai/cookbooks/rerank-search): A short guide on how to apply reranking to R2R results.
- [GraphRAG](https://r2r-docs.sciphi.ai/cookbooks/knowledge-graph): A walkthrough of automatic knowledge graph generation with R2R.
- [Dashboard](https://r2r-docs.sciphi.ai/cookbooks/dashboard): A how-to guide on connecting with the R2R Dashboard.
- [SciPhi Cloud Docs](https://docs.sciphi.ai/): SciPhi Cloud documentation.

# Contributing
As an open-source project in a rapidly changing field, we are extremely open to contributions, no matter how big or small!

These are the most helpful things for us:

- Open a PR for a new feature, improved infrastructure, or better documentation.
- Submit a [feature request](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=feature_request.md&title=) or [bug report](https://github.com/SciPhi-AI/R2R/issues/new?assignees=&labels=&projects=&template=bug_report.md&title=)

### Our Contributors
<a href="https://github.com/SciPhi-AI/R2R/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SciPhi-AI/R2R" />
</a>

