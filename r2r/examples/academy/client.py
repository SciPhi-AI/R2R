import glob
import os

from r2r.client import R2RClient
from r2r.core.utils import generate_id_from_label

# Initialize the client with the base URL of your API
base_url = "http://localhost:8000"  # Change this to your actual API base URL
client = R2RClient(base_url)

titles = {
    "examples/academy/meditations.pdf": "Title: Meditations - Marcus Aurelius",
    "examples/academy/the_republic.pdf": "Title: The Republic - Plato",
}

user_id_0 = generate_id_from_label("user_0")

# Get the directory of the current file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Use this directory in the glob pattern
for file_path in glob.glob(os.path.join(current_dir, "*.pdf")):
    print(f"Uploading and processing file: {file_path}")
    # # Upload and process a file
    document_id = str(generate_id_from_label(file_path))
    metadata = {"user_id": user_id_0, "chunk_prefix": titles[file_path]}
    settings: dict = {}
    upload_response = client.upload_and_process_file(
        document_id, file_path, metadata, settings
    )

prompt = """You are given a user query {query} and a user context {context}. Use the context to answer the given query. """
formatted_prompt = prompt.format(
    query="What are the key themes of these books?",
    context="User Uploads:\nTitle: Meditations - Marcus Aurelius\nTitle: The Republic - Plato",
)
# Perform a search on this file
search_response = client.rag_completion(
    formatted_prompt, 5, filters={"user_id": user_id_0}
)
print(search_response)
