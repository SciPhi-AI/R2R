import asyncio
import glob
import os

import fire

from r2r.client import R2RClient
from r2r.core.utils import generate_id_from_label


class QnAClient:
    def __init__(self, base_url="http://localhost:8001", user_id=None):
        self.client = R2RClient(base_url)
        if not user_id:
            self.user_id = generate_id_from_label("user_id")
        self.titles = {
            "los_angeles-ca-1.pdf": "Title: Los Angelas, CA",
            "san_diego-ca-1.pdf": "Title: San Diego, CA",
            "san_francisco-ca-2.pdf": "Title: San Francisco, CA",
            "sanbernardino-ca-1.pdf": "Title: San Bernadino, CA",
            "lyft_2021.pdf": "Title: Lyft 10k",
        }
        self.history = []

    def ingest(self, document_filter="lyft_2021.pdf"):
        current_file_directory = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(current_file_directory, "..", "data")
        for file_path in glob.glob(os.path.join(data_path, "*")):
            print("file path = ", file_path)
            file_name = file_path.split(os.path.sep)[-1]
            print("file name = ", file_name)
            if (
                # document_filter.lower() == "all"
                # or file_name.lower().startswith(document_filter.lower())
                # file_name.lower() == "lyft_2021.pdf"
                "document"
                in file_name
            ):
                print("ingesting title = ", file_name)
                document_id = generate_id_from_label(file_path)
                print("document_id = ", document_id)
                print("user_id = ", self.user_id)
                metadata = {
                    "user_id": self.user_id,
                    # "chunk_prefix": self.titles[file_name],
                }
                print("metadata = ", metadata)
                settings = {}
                upload_response = self.client.upload_and_process_file(
                    document_id, file_path, metadata, settings
                )
                print("Upload response = ", upload_response)

    def search(self, query):
        query_w_docs = f"""
        User Query:
        {query}

    
        User Docs:
            Title: Los Angelas, CA
            Title: San Diego, CA
            Title: San Francisco, CA
            Title: San Bernadino, CA
        """
        search_response = self.client.search(
            query_w_docs,
            search_limit=25,
            rerank_limit=15,
            filters={"user_id": self.user_id},
        )
        for i, response in enumerate(search_response):
            text = response["metadata"]["text"]
            title, body = text.split("\n", 1)
            print(f"Result {i + 1}: {title}")
            print(body[:500])
            print("\n")

    def rag_completion(self, query, model="gpt-4-turbo-preview"):
        query_w_docs = f"""
        User Query:
        {query}


        User Docs:
            Title: Los Angelas, CA
            Title: San Diego, CA
            Title: San Francisco, CA
            Title: San Bernadino, CA
        """

        rag_response = self.client.rag_completion(
            query_w_docs,
            search_limit=25,
            rerank_limit=15,
            filters={"user_id": self.user_id},
            generation_config={"model": model},
        )
        print("rag_response = ", rag_response)

    def rag_completion_streaming(self, query, model="gpt-4-turbo-preview"):
        async def stream_rag_completion():
            async for chunk in self.client.stream_rag_completion(
                query,
                5,
                filters={"user_id": self.user_id},
                generation_config={"stream": True, "model": model},
            ):
                print(chunk, end="", flush=True)

        asyncio.run(stream_rag_completion())

    def delete_document(self, document_path: str):
        document_id = generate_id_from_label(document_path)
        response = self.client.filtered_deletion("document_id", document_id)
        print("Deletion response = ", response)

    def get_logs(self):
        print("Fetching logs after all steps...")
        logs_response = self.client.get_logs()
        print(f"Logs response:\n{logs_response}\n")

    def get_logs_summary(self):
        print("Fetching logs summary after all steps...")
        logs_summary_response = self.client.get_logs_summary()
        print(f"Logs summary response:\n{logs_summary_response}\n")

    def list_user_ids(self):
        user_ids_response = self.client.get_user_ids()
        print("User IDs response = ", user_ids_response)

    def list_user_documents(self):
        if not self.user_id:
            print("User ID is not set. Cannot fetch documents.")
            return
        user_documents_response = self.client.get_user_documents(self.user_id)
        print(f"Documents for user {self.user_id} = ", user_documents_response)


if __name__ == "__main__":
    fire.Fire(QnAClient)
