import os
from typing import Optional

import fire

from r2r import (
    Document,
    DocumentType,
    GenerationConfig,
    R2RAppBuilder,
    R2RClient,
    R2RConfig,
)

DEFAULT_INGESTION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "aristotle.txt"
)


class R2RQuickstart:
    def __init__(
        self,
        client_server_mode=False,
        base_url="http://localhost:8000",
    ):
        # Optional - pass a `config_path` to `from_json` to override default `config.json`
        config = R2RConfig.from_json()

        self.client_server_mode = client_server_mode
        self.client = R2RClient(base_url)
        self.r2r_app = R2RAppBuilder(config).build()

    def ingest(self, files: list[str] = None) -> None:
        files = files.split(",") if files else [DEFAULT_INGESTION_FILE]

        if not self.client_server_mode:
            # Parse each input file into an R2R document
            # each document is given a deterministic id
            documents = [
                Document(
                    type=DocumentType(file.split(".")[-1]),
                    data=open(file, "rb").read(),
                    metadata={},
                )
                for file in files
            ]
            result = self.r2r_app.ingest_documents(documents)
        else:
            result = self.client.ingest_files(files)
        print(result)

    def search(self, query: str) -> None:
        if not self.client_server_mode:
            result = self.r2r_app.search(query)
        else:
            result = self.client.search(query)
        print(result)

    def rag(self, query: str, model: Optional[str] = "gpt-4o") -> None:
        if not self.client_server_mode:
            result = self.r2r_app.rag(query, GenerationConfig(model=model))
        else:
            result = self.client.rag(query)
        print(result)


if __name__ == "__main__":
    fire.Fire(R2RQuickstart)
