import glob
import os

from r2r.client import R2RClient
from r2r.core.utils import generate_id_from_label

# Initialize the client with the base URL of your API
base_url = "http://localhost:8000"  # Change this to your actual API base URL
client = R2RClient(base_url)

titles = {
    "meditations.pdf": "Title: Meditations - Marcus Aurelius",
    "the_republic.pdf": "Title: The Republic - Plato",
    "test.pdf": "Title: A Test Document",
}

user_id_0 = generate_id_from_label("user_0")

current_file_directory = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(current_file_directory, "..", "data")
print("data_path = ", data_path)
# Use this directory in the glob pattern
for file_path in glob.glob(os.path.join(data_path, "*.pdf")):
    file_name = file_path.split(os.path.sep)[-1]
    print(f"Uploading and processing file: {file_path}")
    # # Upload and process a file
    document_id = str(generate_id_from_label(file_path))
    metadata = {"user_id": user_id_0, "chunk_prefix": titles[file_name]}
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
