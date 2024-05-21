import argparse
import asyncio
import logging
import os
import time
from typing import Optional

import fire
from fastapi.datastructures import UploadFile

from r2r import (
    Document,
    R2RApp,
    R2RConfig,
    R2RPipelineFactory,
    R2RProviderFactory,
    generate_id_from_label,
)


class R2RDemo:
    def __init__(self):
        config = R2RConfig.from_json()

        providers = R2RProviderFactory(config).create_providers()

        pipelines = R2RPipelineFactory(config, providers).create_pipelines()

        self.r2r = R2RApp(config, providers, pipelines)

        root_path = os.path.dirname(os.path.abspath(__file__))
        self.default_files = [
            os.path.join(root_path, "data", "aristotle.txt"),
            os.path.join(root_path, "data", "essay.html"),
            os.path.join(root_path, "data", "lyft_2021.pdf"),
            os.path.join(root_path, "data", "uber_2021.pdf"),
        ]

    def ingest_as_documents(self, file_paths: Optional[list[str]] = None):
        file_paths = file_paths or self.default_files
        documents = []
        for file_path in file_paths:
            with open(file_path, "rb") as f:
                data = f.read()

            documents.append(
                Document(
                    id=generate_id_from_label(file_path),
                    data=data,
                    type=file_path.split(".")[-1],
                    metadata={
                        "title": file_path.split(os.path.sep)[-1],
                    },
                )
            )

        t0 = time.time()
        # self.r2r.ingest_documents(documents)
        t1 = time.time()
        print(f"Time taken to ingest files: {t1-t0:.2f} seconds")

    def ingest_as_files(self, file_paths: Optional[list[str]] = None):
        file_paths = file_paths or self.default_files

        files = [
            UploadFile(
                filename=file_path.split(os.path.sep)[-1],
                file=open(file_path, "rb"),
            )
            for file_path in file_paths
        ]

        # Set file size manually
        for file in files:
            file.file.seek(0, 2)  # Move to the end of the file
            file.size = file.file.tell()  # Get the file size
            file.file.seek(0)  # Move back to the start of the file

        t0 = time.time()
        # self.r2r.ingest_files(files=files)
        t1 = time.time()
        print(f"Time taken to ingest files: {t1-t0:.2f} seconds")


if __name__ == "__main__":
    fire.Fire(R2RDemo)
