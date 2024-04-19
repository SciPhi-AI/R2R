import json

import fire

from r2r.client import R2RClient
from r2r.core.utils import generate_id_from_label


class ChatbotClient:
    def __init__(self, base_url="http://localhost:8000", user_id=None):
        self.client = R2RClient(base_url)
        if not user_id:
            self.user_id = generate_id_from_label("user_id")
        self.history = []

    def rag_chatbot(self, query, model="gpt4-turbo-preview"):
        while query:
            self.history.append({"role": "user", "content": query})
            response = self.client.rag_completion(
                query=json.dumps(self.history)
            )

            if response["completion"]:
                completion_text = response["completion"]["choices"][0][
                    "message"
                ]["content"]
                print("rag_chatbot_response = ", completion_text)
                self.history.append(
                    {"role": "assistant", "content": completion_text}
                )
            else:
                print("rag_chatbot_response = ", response)

            query = input("> ")

    def get_logs(self):
        print("Fetching logs after all steps...")
        logs_response = self.client.get_logs()
        print(f"Logs response:\n{logs_response}\n")

    def get_logs_summary(self):
        print("Fetching logs summary after all steps...")
        logs_summary_response = self.client.get_logs_summary()
        print(f"Logs summary response:\n{logs_summary_response}\n")


if __name__ == "__main__":
    fire.Fire(ChatbotClient)
