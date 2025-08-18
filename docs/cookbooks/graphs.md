R2R allows you to build and analyze knowledge graphs from your documents through a collection-based architecture. The system extracts entities and relationships from documents, enabling richer search capabilities that understand connections between information.

The process works in several key stages:
- Documents are first ingested and entities/relationships are extracted
- Collections serve as containers for documents and their corresponding graphs
- Extracted information is pulled into the collection's graph
- Communities can be built to identify higher-level concepts
- The resulting graph enhances search with relationship-aware queries

Collections in R2R are flexible containers that support multiple documents and provide features for access control and graph management. A document can belong to multiple collections, allowing for different organizational schemes and sharing patterns.

The resulting knowledge graphs improve search accuracy by understanding relationships between concepts rather than just performing traditional document search.

<Steps>
### Ingestion and Extraction
Before we can extract entities and relationships from a document, we must ingest a file. After we've successfully ingested a file, we can `extract` the entities and relationships from document.

In the following script, we fetch *The Gift of the Magi* by O. Henry and ingest it our R2R server. We then begin the extraction process, which may take a few minutes to run.

```python
import requests
from r2r import R2RClient
import tempfile
import os

# Set up the client
client = R2RClient("http://localhost:7272")

# Fetch the text file
url = "https://www.gutenberg.org/cache/epub/7256/pg7256.txt"
response = requests.get(url)

# Create a temporary file
temp_dir = tempfile.gettempdir()
temp_file_path = os.path.join(temp_dir, "gift_of_the_magi.txt")
with open(temp_file_path, 'w') as temp_file:
    temp_file.write(response.text)

# Ingest the file
ingest_response = client.documents.create(file_path=temp_file_path)
document_id = ingest_response["results"]["document_id"]

# Extract entities and relationships
extract_response = client.documents.extract(document_id)

# View extracted knowledge
entities = client.documents.list_entities(document_id)
relationships = client.documents.list_relationships(document_id)

# Clean up the temporary file
os.unlink(temp_file_path)
```

As this script runs, we see indications of successful ingestion and extraction.

<Frame
caption="Both ingestion and extraction were successful, as seen in the R2R Dashboard"
>
    <img src="../images/cookbooks/graphs/document_table_success.png" alt="Successful ingestion and extraction in the R2R dashboard." />
</Frame>

<Frame
caption="Some of the entities extracted from the document"
>
    <img src="../images/cookbooks/graphs/entity_view.png" alt="Viewing the entity in the dashboard." />
</Frame>

### Deduplication

If you would like to deduplicate the extracted entities, you can run the following method. To learn more about deduplication, view our [deduplication documentation here](/documentation/deduplication).

```python
from r2r import R2RClient

# Set up the client
client = R2RClient("http://localhost:7272")

client.documents.deduplicate("20e29a97-c53c-506d-b89c-1f5346befc58")
```

While the exact number of extracted entities and relationships will differ across models, this particular document produces approximately 120 entities, with only 20 distinct entities.

### Managing Collections

Graphs are built within a collection, allowing for us to add many documents to a graph, and to share our graphs with other users. When we ingested the file above, it was added into our default collection.

Each collection has a description which is used in the graph creation process. This can be set by the user, or generated using an LLM.

```python
from r2r import R2RClient

# Set up the client
client = R2RClient("http://localhost:7272")

# Update the description of the default collection
collection_id = "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
update_result = client.collections.update(
    id=collection_id,
    generate_description=True, # LLM generated
)
```

<Frame
    caption="The LLM generated description for our collection"
>
    <img src="../images/cookbooks/graphs/collection_description.png" alt="The resulting description." />
</Frame>

### Pulling Extractions into the Graph

Our graph will not contain the extractions from our documents until we `pull` them into the graph. This gives developers more granular control over the creation and management of graphs.

Recall that we already extracted the entities and relationships for the graph; this means that we can `pull` a document into many graphs without having to rerun the extraction process.

```python
from r2r import R2RClient

# Set up the client
client = R2RClient("http://localhost:7272")

# Pull the extractions from all docments into the default collection
collection_id = "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
client.graphs.pull(
    collection_id=collection_id
)
```

As soon as we `pull` the extractions into the graph, we can begin using the graph in our searches. We can confirm that the entities and relationships were pulled into the collection, as well.

<Frame
caption="Entities are `pulled` in from the document to the collection"
>
    <img src="../images/cookbooks/graphs/entity_view_collection.png" alt="Successful ingestion and extraction in the R2R dashboard." />
</Frame>

<Frame
caption="The distribution of our entities across category"
>
    <img src="../images/cookbooks/graphs/entity_visualization.png" alt="Entity distribution chart." />
</Frame>


### Building Communities

To further enhance our graph we can build communities, which clusters over the entities and relationships inside our graph. This allows us to capture higher-level concepts that exist within our data.

```python
from r2r import R2RClient

# Set up the client
client = R2RClient("http://localhost:7272")

# Build the communities for the default collection
collection_id = "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
client.graphs.build(
    collection_id=collection_id
)
```

We can see that the resulting communities capture overall themes and concepts within the story.

<Frame
caption="The resulting communities, generated from the clustering process"
>
    <img src="../images/cookbooks/graphs/communities.png" alt="The communities generated for the collection." />
</Frame>


### Graph Search

Now that we have built our graph we can query over it. Good questions for graphs might require deep understanding of relationships and ideas that span across multiple documents.

```python
from r2r import R2RClient

# Set up the client
client = R2RClient("http://localhost:7272")

results = client.retrieval.search("""
    What items did Della and Jim each originally own,
    what did they do with those items, and what did they
    ultimately give each other?
    """,
    search_settings={
        "graph_settings": {"enabled": True},
    }
)
```

<Frame
    caption="Performing a multi-hop query over the graph"
>
    <img src="../images/cookbooks/graphs/graph_search.png" alt="Performing a searhc over the graph." />
</Frame>
