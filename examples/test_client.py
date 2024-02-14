from sciphi_r2r.client import SciPhiR2RClient

# Initialize the client with the base URL of your API
base_url = "http://localhost:8000"  # Change this to your actual API base URL
client = SciPhiR2RClient(base_url)

# Example file path for upload
file_path = "test.txt"  # Ensure this file exists in your script's directory

# Upload and process a file
upload_response = client.upload_and_process_file(file_path)
print("Upload and Process File Response:", upload_response)

# Upsert a single text entry
text_entry_response = client.upsert_text_entry("1", "This is a test entry", {"tags": ["example", "test"]})
print("Upsert Text Entry Response:", text_entry_response)

# Upsert multiple text entries
entries = [
    {"id": "2", "text": "Second test entry", "metadata": {"tags": ["bulk", "example"]}},
    {"id": "3", "text": "Third test entry", "metadata": {"tags": ["bulk", "example"]}}
]
bulk_upsert_response = client.upsert_text_entries(entries)
print("Upsert Text Entries Response:", bulk_upsert_response)

# Perform a search
search_response = client.search("test", {"tags": ["example"]}, 5)
print("Search Response:", search_response)

# Execute a RAG completion
rag_completion_response = client.rag_completion("What is the test?", {"tags": ["example"]}, 5)
print("RAG Completion Response:", rag_completion_response)
