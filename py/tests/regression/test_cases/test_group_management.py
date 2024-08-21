import uuid

from tests.regression.test_cases.base import BaseTest


class TestGroupManagement(BaseTest):
    def __init__(self, client):
        super().__init__(client)
        self.admin_email = "admin@example.com"
        self.admin_password = "change_me_immediately"
        self.user_password = "test_password"

        keys_to_ignore = ["group_id", "created_at", "updated_at"]
        self.set_exclude_paths(
            "create_groups_test",
            [f"root['group_1']['results']['{key}']" for key in keys_to_ignore]
            + [
                f"root['group_1']['results']['{key}']"
                for key in keys_to_ignore
            ],
        )

        keys_to_ignore += ["hashed_password"]
        self.set_exclude_paths(
            "add_users_to_groups_test",
            [f"root['user_1']['results']['{key}']" for key in keys_to_ignore]
            + [
                f"root['group_1']['results']['{key}']"
                for key in keys_to_ignore
            ],
        )

    def get_test_cases(self):
        return {
            "create_groups": self.create_groups_test,
            "add_users_to_groups": self.add_users_to_groups_test,
            "group_based_document_access": self.group_based_document_access_test,
            "admin_ingest_documents": self.admin_ingest_documents_test,
            "user_ingest_and_search": self.user_ingest_and_search_test,
            "cleanup": self.cleanup_test,
        }

    def create_groups_test(self, client):
        try:
            client.login(self.admin_email, self.admin_password)
            group_name_1 = f"Test Group 1 {uuid.uuid4()}"
            group_name_2 = f"Test Group 2 {uuid.uuid4()}"
            group_1 = client.create_group(
                group_name_1, "A test group for permissions"
            )
            group_2 = client.create_group(
                group_name_2, "Another test group for permissions"
            )
            self.group_id_1 = group_1["results"]["group_id"]
            self.group_id_2 = group_2["results"]["group_id"]
            return {"group_1": group_1, "group_2": group_2}
        except Exception as e:
            return {"error": str(e)}

    def add_users_to_groups_test(self, client):
        try:
            self.user_email_1 = f"user1_{uuid.uuid4()}@example.com"
            self.user_email_2 = f"user2_{uuid.uuid4()}@example.com"
            user_1 = client.register(self.user_email_1, self.user_password)
            user_2 = client.register(self.user_email_2, self.user_password)
            self.user_id_1 = user_1["results"]["id"]
            self.user_id_2 = user_2["results"]["id"]

            client.add_user_to_group(self.user_id_1, self.group_id_1)
            client.add_user_to_group(self.user_id_2, self.group_id_2)
            client.add_user_to_group(self.user_id_2, self.group_id_1)

            return {"user_1": user_1, "user_2": user_2}
        except Exception as e:
            return {"error": str(e)}

    def group_based_document_access_test(self, client):
        try:
            # Admin ingests a document for group 1
            client.login(self.admin_email, self.admin_password)
            admin_ingest = client.ingest_files(
                file_paths=["tests/regression/test_data/test_document.txt"],
                metadatas=[{"group_ids": [str(self.group_id_1)]}],
            )

            # User 1 searches for documents
            client.login(self.user_email_1, self.user_password)
            user_1_search = client.search("test document")

            # User 2 searches for documents
            client.login(self.user_email_2, self.user_password)
            user_2_search = client.search("test document")

            return {
                "admin_ingest": admin_ingest,
                "user_1_search": user_1_search,
                "user_2_search": user_2_search,
            }
        except Exception as e:
            return {"error": str(e)}

    def admin_ingest_documents_test(self, client):
        try:
            client.login(self.admin_email, self.admin_password)

            # Admin ingests a document for group 1
            admin_ingest_group1 = client.ingest_files(
                file_paths=[
                    "tests/regression/test_data/admin_document_group1.txt"
                ],
                metadatas=[{"group_ids": [str(self.group_id_1)]}],
            )

            # Admin ingests a document for user 1
            admin_ingest_user1 = client.ingest_files(
                file_paths=[
                    "tests/regression/test_data/admin_document_user1.txt"
                ]
            )

            return {
                "admin_ingest_group1": admin_ingest_group1,
                "admin_ingest_user1": admin_ingest_user1,
            }
        except Exception as e:
            return {"error": str(e)}

    def user_ingest_and_search_test(self, client):
        try:
            # User 1 actions
            client.login(self.user_email_1, self.user_password)
            user_1_ingest = client.ingest_files(
                file_paths=["tests/regression/test_data/user1_document.txt"]
            )
            user_1_ingest_group = client.ingest_files(
                file_paths=[
                    "tests/regression/test_data/user1_document_group.txt"
                ],
                metadatas=[{"group_ids": [str(self.group_id_1)]}],
            )

            user_1_search = client.search("document")

            # User 2 actions
            client.login(self.user_email_2, self.user_password)
            user_2_ingest = client.ingest_files(
                file_paths=["tests/regression/test_data/user2_document.txt"]
            )
            user_2_search = client.search("document")

            return {
                "user_1_ingest": user_1_ingest,
                "user_1_search": user_1_search,
                "user_2_ingest": user_2_ingest,
                "user_2_search": user_2_search,
            }
        except Exception as e:
            return {"error": str(e)}

    def cleanup_test(self, client):
        try:
            client.login(self.admin_email, self.admin_password)
            client.delete_group(self.group_id_1)
            client.delete_group(self.group_id_2)
            client.delete_user(self.user_id_1, self.user_password)
            client.delete_user(self.user_id_2, self.user_password)
            return {"status": "cleanup completed"}
        except Exception as e:
            return {"error": str(e)}
