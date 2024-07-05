import os
import uuid
from typing import List, Optional, Union

import fire

from r2r import R2R, Document, R2RClient, R2RConfig, generate_id_from_label


class SampleDataIngestor:
    USER_IDS = [
        "063edaf8-3e63-4cb9-a4d6-a855f36376c3",
        "45c3f5a8-bcbe-43b1-9b20-51c07fd79f14",
        "c6c23d85-6217-4caa-b391-91ec0021a000",
        None,
    ]

    def __init__(
        self,
        config_path: Optional[str] = None,
        client_server_mode: bool = True,
        base_url: str = "http://localhost:8000",
    ):
        if client_server_mode:
            self.client = R2RClient(base_url)
        else:
            config = (
                R2RConfig.from_json(config_path)
                if config_path
                else R2RConfig.from_json()
            )
            self.app = R2R(config=config)

    @staticmethod
    def get_sample_files() -> List[str]:
        examples_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".."
        )

        return [
            os.path.join(examples_dir, "data", "aristotle.txt"),
            os.path.join(examples_dir, "data", "got.txt"),
            os.path.join(examples_dir, "data", "screen_shot.png"),
            os.path.join(examples_dir, "data", "pg_essay_1.html"),
            os.path.join(examples_dir, "data", "pg_essay_2.html"),
            os.path.join(examples_dir, "data", "pg_essay_3.html"),
            os.path.join(examples_dir, "data", "pg_essay_4.html"),
            os.path.join(examples_dir, "data", "pg_essay_5.html"),
            os.path.join(examples_dir, "data", "lyft_2021.pdf"),
            os.path.join(examples_dir, "data", "uber_2021.pdf"),
            os.path.join(examples_dir, "data", "sample.mp3"),
            os.path.join(examples_dir, "data", "sample2.mp3"),
        ]

    def create_document(
        self, file_path: str, user_id: Optional[uuid.UUID]
    ) -> Document:
        with open(file_path, "rb") as f:
            data = f.read()
        return Document(
            id=generate_id_from_label(os.path.basename(file_path)),
            data=data,
            type=file_path.split(".")[-1],
            metadata={
                "user_id": user_id,
                "title": os.path.basename(file_path),
            },
        )

    def ingest_documents(self, documents: List[Document]) -> Union[dict, str]:
        if hasattr(self, "client"):
            documents_dicts = [doc.dict() for doc in documents]
            return self.client.ingest_documents(documents_dicts, monitor=True)
        else:
            return self.app.ingest_documents(documents)

    def process_files(
        self, file_paths: List[str], user_ids: List[Optional[uuid.UUID]]
    ) -> List[Document]:
        return [
            self.create_document(file_path, user_ids[i % len(user_ids)])
            for i, file_path in enumerate(file_paths)
        ]

    def ingest_sample_files(self):
        sample_files = self.get_sample_files()
        user_ids = [
            uuid.UUID(user_id) if user_id else None
            for user_id in self.USER_IDS
        ]

        documents = self.process_files(sample_files, user_ids)
        response = self.ingest_documents(documents)

        print("Sample files ingested successfully.")
        print(response)

    def ingest_sample_file(self):
        sample_files = self.get_sample_files()
        user_id = uuid.UUID(self.USER_IDS[0])

        document = self.create_document(sample_files[0], user_id)
        response = self.ingest_documents([document])

        print("First sample file ingested successfully.")
        print(response)


if __name__ == "__main__":
    fire.Fire(SampleDataIngestor)

    # import os
# import uuid
# from typing import List, Optional, Union

# import fire
# from r2r import R2R, R2RClient, Document, generate_id_from_label

# class SampleDataIngestor:
#     USER_IDS = [
#         "063edaf8-3e63-4cb9-a4d6-a855f36376c3",
#         "45c3f5a8-bcbe-43b1-9b20-51c07fd79f14",
#         "c6c23d85-6217-4caa-b391-91ec0021a000",
#         None,
#     ]

#     def __init__(self, client_server_mode: bool = True, base_url: Optional[str] = None):
#         if client_server_mode:
#             self.base_url = base_url or "http://localhost:8000"
#             self.client = R2RClient(self.base_url)
#         else:
#             self.app = R2R()

#     @staticmethod
#     def get_sample_files() -> List[str]:
#         examples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

#         return [
#             os.path.join(examples_dir, "data", "aristotle.txt"),
#             os.path.join(examples_dir, "data", "got.txt"),
#             os.path.join(examples_dir, "data", "screen_shot.png"),
#             os.path.join(examples_dir, "data", "pg_essay_1.html"),
#             os.path.join(examples_dir, "data", "pg_essay_2.html"),
#             os.path.join(examples_dir, "data", "pg_essay_3.html"),
#             os.path.join(examples_dir, "data", "pg_essay_4.html"),
#             os.path.join(examples_dir, "data", "pg_essay_5.html"),
#             os.path.join(examples_dir, "data", "lyft_2021.pdf"),
#             os.path.join(examples_dir, "data", "uber_2021.pdf"),
#             os.path.join(examples_dir, "data", "sample.mp3"),
#             os.path.join(examples_dir, "data", "sample2.mp3"),
#         ]

#     def create_document(self, file_path: str, user_id: Optional[uuid.UUID]) -> Document:
#         with open(file_path, "rb") as f:
#             data = f.read()
#         return Document(
#             id=generate_id_from_label(os.path.basename(file_path)),
#             data=data,
#             type=file_path.split(".")[-1],
#             metadata={
#                 "user_id": user_id,
#                 "title": os.path.basename(file_path),
#             },
#         )

#     def ingest_documents(self, documents: List[Document]) -> Union[dict, str]:
#         if hasattr(self, "client"):
#             documents_dicts = [doc.dict() for doc in documents]
#             return self.client.ingest_documents(documents_dicts, monitor=True)
#         else:
#             return self.app.ingest_documents(documents)

#     def process_files(self, file_paths: List[str], user_ids: List[Optional[uuid.UUID]]) -> List[Document]:
#         return [
#             self.create_document(file_path, user_ids[i % len(user_ids)])
#             for i, file_path in enumerate(file_paths)
#         ]

#     def ingest_sample_files(self):
#         sample_files = self.get_sample_files()
#         user_ids = [uuid.UUID(user_id) if user_id else None for user_id in self.USER_IDS]

#         documents = self.process_files(sample_files, user_ids)
#         response = self.ingest_documents(documents)

#         print("Sample files ingested successfully.")
#         print(response)

#     def ingest_sample_file(self):
#         sample_files = self.get_sample_files()
#         user_id = uuid.UUID(self.USER_IDS[0])

#         document = self.create_document(sample_files[0], user_id)
#         response = self.ingest_documents([document])

#         print("First sample file ingested successfully.")
#         print(response)

# if __name__ == "__main__":
#     fire.Fire(SampleDataIngestion)
