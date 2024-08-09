import uuid

from tests.regression.test_cases.base import BaseTest


class TestUserManagement(BaseTest):
    def __init__(self, client):
        super().__init__(client)
        self.set_exclude_paths(
            "register_user",
            [
                f"root['results']['{field}']"
                for field in [
                    "id",
                    "email",
                    "created_at",
                    "updated_at",
                    "hashed_password",
                ]
            ],
        )
        self.set_exclude_paths(
            "login_user",
            [
                f"root['results']['{field}']"
                for field in ["access_token", "refresh_token"]
            ],
        )
        self.set_exclude_paths("user_info", [])

    def get_test_cases(self):
        return {
            "register_user": lambda client: self.register_user_test(client),
            "login_user": lambda client: self.login_user_test(client),
            "user_info": lambda client: self.user_info_test(client),
        }

    def register_user_test(self, client):
        try:
            email = f"test@example.com"
            password = "password123"
            return client.register(email, password)
        except:
            pass

        email = f"test_{uuid.uuid4()}@example.com"
        password = "password123"
        return client.register(email, password)

    def login_user_test(self, client):
        email = "test@example.com"  # Use a known test user
        password = "password123"
        return client.login(email, password)

    def user_info_test(self, client):
        return client.user()
