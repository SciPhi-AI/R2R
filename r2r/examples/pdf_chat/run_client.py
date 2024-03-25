import asyncio
import glob
import os
import uuid

import fire

from r2r.client import R2RClient
from r2r.core.utils import generate_id_from_label


class PDFChat:
    def __init__(self, base_url="http://localhost:8000", user_id=None):
        self.client = R2RClient(base_url)
        if not user_id:
            self.user_id = generate_id_from_label("user_id")
        self.titles = {
            "meditations.pdf": "Title: Meditations - Marcus Aurelius",
            # uncomment the following line to add more documents
            # "the_republic.pdf": "Title: The Republic - Plato",
        }

    def ingest(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for file_path in glob.glob(os.path.join(current_dir, "*.pdf")):
            file_name = file_path.split(os.path.sep)[-1]
            if file_name in self.titles:
                document_id = generate_id_from_label(file_path)
                metadata = {
                    "user_id": self.user_id,
                    "chunk_prefix": self.titles[file_name],
                }
                settings = {}
                upload_response = self.client.upload_and_process_file(
                    document_id, file_path, metadata, settings
                )
                print("Upload response = ", upload_response)

    def search(self, query):
        search_response = self.client.search(
            query,
            5,
            filters={"user_id": self.user_id},
        )
        for i, response in enumerate(search_response):
            text = response["metadata"]["text"]
            title, body = text.split("\n", 1)
            print(f"Result {i + 1}: {title}")
            print(body[:500])
            print("\n")

    def rag_completion(self, query):
        rag_response = self.client.rag_completion(
            query,
            5,
            filters={"user_id": self.user_id},
        )
        print("rag_response = ", rag_response)

    def rag_completion_streaming(self, query):
        async def stream_rag_completion():
            async for chunk in self.client.stream_rag_completion(
                query,
                5,
                filters={"user_id": self.user_id},
                generation_config={"stream": True},
            ):
                print(chunk, end="", flush=True)

        asyncio.run(stream_rag_completion())

    def delete_document(self, document_path: str):
        document_id = generate_id_from_label(document_path)
        response = self.client.filtered_deletion("document_id", document_id)
        print("Deletion response = ", response)


if __name__ == "__main__":
    fire.Fire(PDFChat)
