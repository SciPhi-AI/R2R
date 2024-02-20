import uuid

from sciphi_r2r.client import SciPhiR2RClient

# Initialize the client with the base URL of your API
base_url = "http://localhost:8000"  # Change this to your actual API base URL
client = SciPhiR2RClient(base_url)

# Example file path for upload
# file_path = "config.json"  # Ensure this file exists in your script's directory

# Upload and process a file
# upload_response = client.upload_and_process_file(file_path)
# print("Upload and Process File Response:", upload_response)
import uuid

from sciphi_r2r.client import SciPhiR2RClient

# Initialize the client with the base URL of your API
base_url = "http://localhost:8000"  # Change this to your actual API base URL
client = SciPhiR2RClient(base_url)

# Upsert a single entry
entry_response = client.upsert_entry(
    str(uuid.uuid5(uuid.NAMESPACE_DNS, "doc 1")),  # document_id
    {"txt": "This is a test entry"},
    {"tags": ["example", "test"]},
)
print("Upsert Entry Response:", entry_response)

# Upsert multiple entries
entries = [
    {
        "document_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "doc 2")),
        "blobs": {"txt": "Second test entry"},
        "metadata": {"tags": "bulk"},
    },
    {
        "document_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "doc 3")),
        "blobs": {"txt": "Third test entry"},
        "metadata": {"tags": "example"},
    },
]
bulk_upsert_response = client.upsert_entries(entries)
print("Upsert Entries Response:", bulk_upsert_response)

# Perform a search
search_response = client.search("test", 5)
print("Search Response:", search_response)

# Perform a search w/ filter
search_response = client.search("test", 5, filters={"tags": "bulk"})
print("Search w/ filter Response:", search_response)

# Delete a document
response = client.filtered_deletion(
    "document_id", str(uuid.uuid5(uuid.NAMESPACE_DNS, "doc 2"))
)
print("Deletion Response:", response)

# Perform a search w/ filter after deletion
search_response = client.search("test", 5, filters={"tags": "bulk"})
print("Search w/ filter + deletion Response:", search_response)

# # Execute a RAG completion
# rag_completion_response = client.rag_completion(
#     "What is the test?", 5
# )
# print("RAG Completion Response:", rag_completion_response)
