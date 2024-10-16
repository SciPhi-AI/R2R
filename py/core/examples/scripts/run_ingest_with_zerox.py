import os
import time

from r2r import R2RClient

if __name__ == "__main__":
    client = R2RClient(base_url="http://localhost:7272")
    script_path = os.path.dirname(__file__)
    sample_file = os.path.join(script_path, "..", "data", "graphrag.pdf")

    ingest_response = client.ingest_files(
        file_paths=[sample_file],
        ingestion_config={"parser_overrides": {"pdf": "zerox"}},
    )
    time.sleep(60)
