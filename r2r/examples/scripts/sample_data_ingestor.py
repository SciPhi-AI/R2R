import os
import uuid
from typing import List, Optional, Union

import fire

from r2r import R2R, R2RClient, R2RConfig


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
            # os.path.join(examples_dir, "data", "got.txt"),
            # # os.path.join(examples_dir, "data", "screen_shot.png"),
            # os.path.join(examples_dir, "data", "pg_essay_1.html"),
            # os.path.join(examples_dir, "data", "pg_essay_2.html"),
            # os.path.join(examples_dir, "data", "pg_essay_3.html"),
            # os.path.join(examples_dir, "data", "pg_essay_4.html"),
            # os.path.join(examples_dir, "data", "pg_essay_5.html"),
            os.path.join(examples_dir, "data", "lyft_2021.pdf"),
            # os.path.join(examples_dir, "data", "uber_2021.pdf"),
            # os.path.join(examples_dir, "data", "sample.mp3"),
            # os.path.join(examples_dir, "data", "sample2.mp3"),
        ]

    def ingest_files(
        self,
        file_paths: List[str],
        user_ids: List[Optional[uuid.UUID]],
        no_media: bool = True,
    ) -> Union[dict, str]:
        if no_media:
            excluded_types = ["jpeg", "jpg", "png", "svg", "mp3", "mp4"]
            file_paths = [
                file_path
                for file_path in file_paths
                if file_path.split(".")[-1].lower() not in excluded_types
            ]

        files = []
        metadata = []

        for i, file_path in enumerate(file_paths):
            user_id = (
                user_ids[i % len(user_ids)]
                if user_ids[i % len(user_ids)]
                else None
            )
            data = {"title": os.path.basename(file_path)}
            if user_id:
                data["user_id"] = str(user_id)
            metadata.append(data)

        if hasattr(self, "client"):
            return self.client.ingest_files(file_paths, metadata, monitor=True)
        else:
            try:
                with open(file_path, "rb") as f:
                    files.append(("files", (os.path.basename(file_path), f)))

                return self.app.ingest_files(files, metadata)
            except Exception as e:
                raise ValueError(f"Error ingesting file {file_path}: {e}")
            finally:
                # Close all opened files
                for _, (_, file, _) in files:
                    file.close()

    def ingest_sample_files(self, no_media: bool = True):
        sample_files = self.get_sample_files()
        user_ids = [
            uuid.UUID(user_id) if user_id else None
            for user_id in self.USER_IDS
        ]

        response = self.ingest_files(sample_files, user_ids, no_media)

        print("Sample files ingested successfully.")
        print(response)

    def ingest_sample_file(self, no_media: bool = True):
        sample_files = self.get_sample_files()
        user_id = uuid.UUID(self.USER_IDS[0])

        response = self.ingest_files([sample_files[0]], [user_id], no_media)

        print("First sample file ingested successfully.")
        print(response)


if __name__ == "__main__":
    fire.Fire(SampleDataIngestor)
