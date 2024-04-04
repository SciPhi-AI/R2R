import os
import tempfile
from typing import Optional

import requests

from ..base import Adapter


class ReductoAPIError(Exception):
    """Custom exception class for Reducto API errors."""

    pass


class ReductoAdapter(Adapter[dict]):
    def __init__(
        self, s3_bucket: Optional[str] = None, api_key: Optional[str] = None
    ):
        try:
            import boto3
        except ImportError:
            raise ImportError("Please install boto3 to use the ReductoAdapter")

        api_key = api_key or os.getenv("REDUCTO_API_KEY")
        s3_bucket = s3_bucket or os.getenv("AWS_S3_BUCKET")

        if not api_key:
            raise ValueError(
                "Reducto API key not found. Please set the REDUCTO_API_KEY environment variable."
            )
        if not s3_bucket:
            raise ValueError(
                "AWS S3 bucket name not found. Please set the AWS_S3_BUCKET_NAME environment variable."
            )

        self.api_key = api_key
        self.s3_bucket = s3_bucket
        self.s3 = boto3.client("s3")

    def adapt(self, data: bytes) -> list[str]:
        # Upload the file to S3

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(data)
            file_path = temp_file.name
            file_name = os.path.basename(file_path)

        self.s3.upload_file(file_path, self.s3_bucket, file_name)
        os.unlink(file_path)

        # Generate the presigned URL
        presigned_url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.s3_bucket, "Key": file_name},
            ExpiresIn=3600,  # URL expires in 1 hour (3600 seconds)
        )

        # Prepare the request payload
        payload = {
            "document_url": presigned_url,
            "config": {
                "chunk_size": None,
                "disable_chunking": False,
                "mode": "document",
                "table_summary": True,
                "figure_summary": False,
                "chart_extract": False,
                "enrich": False,
                "merge_tables": False,
                "dpi": 200,
            },
        }

        # Make the API request
        url = "https://v1.api.reducto.ai/parse"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers)

        # Check the response status code
        if response.status_code == 200:
            response_json = response.json()
            result = response_json["result"]
            for chunk in result["chunks"]:
                yield chunk["content"]
        else:
            raise ReductoAPIError(
                f"Error processing document. Status code: {response.status_code}. Error message: {response.text}"
            )
