import glob
import uuid

from r2r.client import R2RClient

# Initialize the client with the base URL of your API
base_url = "http://localhost:8000"  # Change this to your actual API base URL
client = R2RClient(base_url)

titles = {
    "examples/academy/meditations.pdf": "Title: Meditations - Marcus Aurelius",
    "examples/academy/the_republic.pdf": "Title: The Republic - Plato",

}

user_id_0 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "user_0"))

for file_path in glob.glob("examples/academy/*.pdf"):
    print(f"Uploading and processing file: {file_path}")
    # # Upload and process a file
    document_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_path))
    metadata = {"user_id": user_id_0, "chunk_prefix": titles[file_path]}
    settings = {}
    upload_response = client.upload_and_process_file(
        document_id, file_path, metadata, settings
    )

prompt = """You are given a user query {query} and a use context {context}. Use the context to answer the query. Pay close attention to the title of each given source to ensure it is consistent with the query. Use line item references to like [1], [2], ... refer to specifically numbered items in the provided context. The query is: {query}"""
prompt.format(
    query="What are the key themes of these books?",
    context="User Uploads:\nTitle: Meditations - Marcus Aurelius\nTitle: The Republic - Plato",
)
# Perform a search on this file
search_response = client.rag_completion(
    prompt, 5, filters={"user_id": user_id_0}
)
print(search_response)
