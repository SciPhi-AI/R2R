import uuid

from tests.regression.test_cases.base import BaseTest


class TestUserManagement(BaseTest):
    VARIABLE_USER_FIELDS = [
        "id",
        "email",
        "created_at",
        "updated_at",
        "hashed_password",
        "access_token",
        "refresh_token",
    ]

    def __init__(self, client):
        super().__init__(client)
        self.set_exclude_paths(
            "register_user",
            [
                f"root['{field}']"
                for field in TestUserManagement.VARIABLE_USER_FIELDS
            ],
        )
        self.set_exclude_paths(
            "login_user",
            [
                f"root['{field}']"
                for field in ["access_token", "refresh_token"]
            ],
        )
        self.set_exclude_paths(
            "user_info",
            [
                f"root['{field}']"
                for field in TestUserManagement.VARIABLE_USER_FIELDS
            ],
        )
        self.set_exclude_paths(
            "change_password",
            [
                f"root['{field}']"
                for field in TestUserManagement.VARIABLE_USER_FIELDS
            ],
        )
        self.set_exclude_paths(
            "update_profile",
            [
                f"root['{field}']"
                for field in TestUserManagement.VARIABLE_USER_FIELDS
            ],
        )
        self.set_exclude_paths(
            "refresh_token",
            [
                f"root['{field}']"
                for field in TestUserManagement.VARIABLE_USER_FIELDS
            ],
        )
        self.user_id_string = str(uuid.uuid4()).split("-")[0]
        self.user_id_string_2 = str(uuid.uuid4()).split("-")[0]

    def get_test_cases(self):
        return {
            "register_user": lambda client: self.register_user_test(client),
            "login_user": lambda client: self.login_user_test(client),
            "user_info": lambda client: self.user_info_test(client),
            "change_password": lambda client: self.change_password_test(
                client
            ),
            # "reset_password": lambda client: self.reset_password_test(client),
            "update_profile": lambda client: self.update_profile_test(client),
            "refresh_token": lambda client: self.refresh_token_test(client),
            "superuser_test": lambda client: self.superuser_test(client),
            "logout": lambda client: self.logout_test(client),
            "delete_account": lambda client: self.delete_user_test(client),
            "login_user": lambda client: self.login_user_test(client),
            "refresh_token": lambda client: self.refresh_token_test(client),
        }

    def register_user_test(self, client):
        try:
            email = f"test_{self.user_id_string}@example.com"
            password = "password123"
            user = client.register(email, password)
            self.user = user
            return user
        except Exception as e:
            return {"results": str(e)}

    def login_user_test(self, client):
        try:
            email = f"test_{self.user_id_string}@example.com"
            password = "password123"
            login = client.login(email, password)
            return login
        except Exception as e:
            return {"results": str(e)}

    def user_info_test(self, client):
        try:
            return client.user()
        except Exception as e:
            return {"results": str(e)}

    def change_password_test(self, client):
        try:
            return client.change_password("password123", "new_password")
        except Exception as e:
            return {"results": str(e)}

    # def reset_password_test(self, client):
    #     try:
    #         reset_request = client.request_password_reset("test@example.com")
    #         # In a real scenario, we'd need to get the reset token from the email
    #         reset_token = "mock_reset_token"
    #         return client.confirm_password_reset(reset_token, "new_password")
    #     except Exception as e:
    #         return {"results": str(e)}

    def update_profile_test(self, client):
        try:
            return client.update_user(name="John Doe", bio="R2R enthusiast")
        except Exception as e:
            return {"results": str(e)}

    def delete_user_test(self, client):
        try:
            email = f"test_{self.user_id_string_2}@example.com"
            password = "password123"
            user = client.register(email, password)

            return client.delete_user(user["results"]["id"], "password123")
        except Exception as e:
            return {"results": str(e)}

    def refresh_token_test(self, client):
        try:
            return client.refresh_access_token()
        except Exception as e:
            return {"results": str(e)}

    def superuser_test(self, client):
        try:
            # Login as admin
            client.login("admin@example.com", "change_me_immediately")
            return client.users_overview()
        except Exception as e:
            return {"results": str(e)}

    def logout_test(self, client):
        try:
            return client.logout()
        except Exception as e:
            return {"results": str(e)}
