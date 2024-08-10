import os

from r2r import R2RException
from tests.regression.test_cases.base import BaseTest


class TestDocumentManagement(BaseTest):

    CHUNKS_FILE_ID = "b736292c-11e6-5453-9686-055da3edb866"
    UPDATE_FILE_ID = "93123a68-d668-51de-8291-92162730dc87"
    DELETE_FILE_ID = "b736292c-11e6-5453-9686-055da3edb866"

    def __init__(self, client):
        super().__init__(client)
        self.set_exclude_paths(
            "documents_overview",
            [
                f"root['results'][%i]['{field}']"
                for field in ["created_at", "updated_at"]
                for i in range(20)
            ],
        )

    def get_test_cases(self):
        return {
            "ingest_sample_files": lambda client: self.ingest_sample_files_test(
                client
            ),
            "reingest_sample_file": lambda client: self.ingest_sample_files_test(
                client
            ),
            "documents_overview": lambda client: self.documents_overview_test(
                client
            ),
            "document_chunks_test": lambda client: self.document_chunks_test(
                client
            ),
            "update_document": lambda client: self.update_document_test(
                client
            ),
            "delete_document": lambda client: self.delete_document_test(
                client
            ),
            "rerun_documents_overview": lambda client: self.documents_overview_test(
                client
            ),
            "rerun_document_chunks_test": lambda client: self.document_chunks_test(
                client
            ),
        }

    def ingest_sample_files_test(self, client):
        file_path = os.path.abspath(__file__)
        data_path = os.path.join(
            os.path.dirname(file_path),
            "..",
            "..",
            "..",
            "r2r",
            "examples",
            "data",
        )
        try:
            return client.ingest_files(
                [
                    os.path.join(data_path, file_name)
                    for file_name in os.listdir(data_path)
                ]
            )
        except R2RException as e:
            return {"results": str(e)}

    def documents_overview_test(self, client):
        try:
            return client.documents_overview()
        except R2RException as e:
            return {"results": str(e)}

    def document_chunks_test(self, client):
        try:
            # Now delete the file
            chunks_response = client.document_chunks(
                TestDocumentManagement.CHUNKS_FILE_ID
            )
            return chunks_response
        except R2RException as e:
            return {"results": str(e)}

    def update_document_test(self, client):
        try:
            # Now update the file
            file_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "r2r",
                "examples",
                "data",
                "aristotle_v2.txt",
            )
            update_response = client.update_files(
                [file_path], [TestDocumentManagement.UPDATE_FILE_ID]
            )
            return update_response
        except R2RException as e:
            return {"results": str(e)}

    def delete_document_test(self, client):
        try:
            # Now delete the file
            delete_response = client.delete(
                ["document_id"], [TestDocumentManagement.DELETE_FILE_ID]
            )
            return delete_response
        except R2RException as e:
            return {"results": str(e)}
