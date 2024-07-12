import os
import uuid
from typing import TYPE_CHECKING

import fire

if TYPE_CHECKING:
    from r2r.main.execution import R2RExecutionWrapper


class SampleDataIngestor:
    USER_IDS = [
        "063edaf8-3e63-4cb9-a4d6-a855f36376c3",
        "45c3f5a8-bcbe-43b1-9b20-51c07fd79f14",
        "c6c23d85-6217-4caa-b391-91ec0021a000",
        None,
    ]

    def __init__(
        self,
        executor: "R2RExecutionWrapper",
    ):
        self.executor = executor

    @staticmethod
    def get_sample_files(no_media: bool = True) -> list[str]:
        examples_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".."
        )

        files = [
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
        if no_media:
            excluded_types = ["jpeg", "jpg", "png", "svg", "mp3", "mp4"]
            files = [
                file_path
                for file_path in files
                if file_path.split(".")[-1].lower() not in excluded_types
            ]
        return files

    def ingest_sample_files(self, no_media: bool = True):
        sample_files = self.get_sample_files(no_media)
        user_ids = [
            uuid.UUID(user_id) if user_id else None
            for user_id in self.USER_IDS
        ]

        response = self.executor.ingest_files(
            sample_files,
            [
                {"user_id": user_ids[it % len(user_ids)]}
                for it in range(len(sample_files))
            ],
        )
        return response

    def ingest_sample_file(self, no_media: bool = True, option: int = 0):
        sample_files = self.get_sample_files()
        user_id = uuid.UUID(self.USER_IDS[option % len(self.USER_IDS)])

        response = self.executor.ingest_files(
            [sample_files[option]], [{"user_id": user_id}]
        )
        return response


if __name__ == "__main__":
    fire.Fire(SampleDataIngestor)
