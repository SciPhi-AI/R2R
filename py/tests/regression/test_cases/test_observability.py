from tests.regression.test_cases.base import BaseTest


class TestObservability(BaseTest):
    def __init__(self, client):
        super().__init__(client)
        # Add exclude_paths as needed

    def get_test_cases(self):
        return {
            "users_overview": lambda client: self.users_overview_test(client),
            "logs": lambda client: self.logs_test(client),
            "analytics": lambda client: self.analytics_test(client),
        }

    def users_overview_test(self, client):
        return client.users_overview()

    def logs_test(self, client):
        return client.logs()

    def analytics_test(self, client):
        return client.analytics(
            {"search_latencies": "search_latency"},
            {"search_latencies": ["basic_statistics", "search_latency"]},
        )
