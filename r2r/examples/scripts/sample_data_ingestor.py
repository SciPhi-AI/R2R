import os
from typing import TYPE_CHECKING

import fire

if TYPE_CHECKING:
    from r2r.main.execution import R2RExecutionWrapper


class SampleDataIngestor:
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

        response = self.executor.ingest_files(
            sample_files,
        )
        return response

    def ingest_sample_file(self, no_media: bool = True, option: int = 0):
        sample_files = self.get_sample_files()

        response = self.executor.ingest_files(
            [sample_files[option]],
        )
        return response


if __name__ == "__main__":
    fire.Fire(SampleDataIngestor)
