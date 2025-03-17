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
