# Basic Example
This example illustrates how to use the R2R framework to ingest PDF data, conduct searches, and generate responses through a basic local server and client setup. This demonstrates the framework's advanced document processing and retrieval-augmented generation capabilities.


## Step 0: Dependencies
Install the repo locally
```
git clone git@github.com:SciPhi-AI/r2r.git
cd r2r
```
And make sure you have the necessary dependencies installed and the environment variables set.
```bash
pip install 'r2r[all]'
export OPENAI_API_KEY="replace with your openai key"
export LOCAL_DB_PATH=local.sqlite
```

## Step 1: Launch the Basic Application Server

To launch the basic application server, run the following command:

```bash
python -m r2r.examples.servers.basic_pipeline
```

This command starts the backend server with the basic RAG pipeline, which includes the ingestion, embedding, and RAG pipelines served via FastAPI.

## Step 2: Ingest the Demo PDF Data Using a Client

To ingest the demo PDF data, use the following command:

```bash
python -m r2r.examples.clients.run_basic_client_ext ingest
```

This command uploads the `meditations.pdf` file located in the `examples/pdf_chat` directory and processes it using the ingestion pipeline. The output should be similar to:

```
Upload response = {'message': "File 'meditations.pdf' processed and saved at '/path/to/uploads/meditations.pdf'"}
```

## Step 3: Perform a Search Using a Client

To perform a search on the ingested PDF data, run the following command:

```bash
python -m r2r.examples.clients.run_basic_client_ext search "what is the meditations about?"
```

This command searches the ingested PDF data for information related to the query "what is the meditations about?". The output should include relevant text snippets from the PDF, such as:

```
Result 1: Title: Meditations - Marcus Aurelius
Middle things, Book 7,XXV. TheStoics divided allthings into
virtue, vice ...
```

## Step 4: Perform a Completion with RAG

To generate a completion using the RAG (Retrieval-Augmented Generation) pipeline, run the following command:

```bash
python -m r2r.examples.clients.run_basic_client_ext rag_completion "what is the meditations about?"
```

This command utilizes the RAG pipeline to generate a comprehensive answer to the query "what is the meditations about?". The output should include a detailed response based on the ingested PDF data, similar to:

```
{
  ...
  'message': {'content': '"Meditations" by Marcus Aurelius is a series of personal writings by the Roman Emperor, reflecting his thoughts on Stoic philosophy. The text delves into the nature of the human mind, ethics, and the universe, advocating for a life of virtue, rationality, and self-restraint. Aurelius discusses the importance of understanding one\'s place in the cosmos and the need to live in harmony with nature and society. He emphasizes the significance of inner peace, the control of one\'s desires and emotions, and the pursuit of goodness as the highest goal. Through his meditations, Aurelius seeks to provide guidance on leading a meaningful life, focusing on personal improvement and the development of a moral character in accordance with Stoic principles.'}
  ...
}
```

The RAG pipeline retrieves relevant information from the ingested PDF data and generates a coherent and informative response to the given query.

## Step 5: Perform Streaming Completion with RAG
To generate a streaming completion, run the following command:
```bash
python -m r2r.examples.clients.run_basic_client_ext rag_completion_streaming "what is the meditations about?"
```
You should be able to see the response getting streamed to your console as it's getting generated.


## Step 6: Get Server logs
To get server logs using the client, run the following command:
```
python -m r2r.examples.clients.run_basic_client_ext get_logs
```

Or, if you just want the summary of the logs, run:
```
python -m r2r.examples.clients.run_basic_client_ext get_logs_summary
```


## Optional Step 7: Configure the Application

<a name="configjson"></a>

During the example pipeline creation, a default `config.json` is loaded and passed to the pipeline. It provides settings for various components, including the database provider, LLM settings, embedding settings, parsing logic, and more.

The default values for the configuration are shown below:

```json
{
  "vector_database": {
    "provider": "local",
    "collection_name": "demo-v1-test"
  },
  "evals": {
    "provider": "deepeval",
    "frequency": 0.25
  },
  "embedding": {
    "provider": "openai",
    "model": "text-embedding-3-small",
    "dimension": 1536,
    "batch_size": 32
  },
  "text_splitter": {
    "chunk_size": 512,
    "chunk_overlap": 20
  },
  "language_model": {
    "provider": "litellm",
    "model": "gpt-4-0125-preview",
    "temperature": 0.1,
    "top_p": 0.9,
    "top_k": 128,
    "max_tokens_to_sample": 1024,
    "do_stream": false
  },
  "logging": {
    "provider": "local",
    "level": "INFO",
    "name": "r2r",
    "database": "demo_logs_v1"
  }
}
```

_Note: For a full list of options, see [Config Setup](../core_features/config.mdx)._

The pipeline consists of three main components: `Ingestion`, `Embedding`, and `RAG`, along with `Logging`.

To launch your own custom application pipeline, you can use the following code:

```python
class E2EPipelineFactory:
    ...
    app = E2EPipelineFactory.create_pipeline(
        # override with your own custom ingestion pipeline
        ingestion_pipeline_impl=BasicIngestionPipeline,
        # override with your own custom embedding pipeline
        embedding_pipeline_impl=BasicEmbeddingPipeline,
        # override with your own custom RAG pipeline
        rag_pipeline_impl=BasicRAGPipeline,
        # override with your own config.json
        config=R2RConfig.load_config("your_config_path.json")
    )
```

This code allows you to customize the pipeline components and provide your own configuration file.