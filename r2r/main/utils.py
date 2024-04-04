import json
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Any, Union

from fastapi.middleware.cors import CORSMiddleware

from r2r.core import BasicDocument

logger = logging.getLogger(__name__)


# Function to find the project root by looking for a .git folder or setup.py file
def find_project_root(current_dir):
    for parent in current_dir.parents:
        if any((parent / marker).exists() for marker in [".git", "setup.py"]):
            return parent
    return current_dir  # Fallback to current dir if no marker found


REQUIRED_KEYS: dict[str, list] = {
    "embedding": ["provider", "model"],
    "evals": ["provider", "frequency"],
    "language_model": ["provider"],
    "logging_database": ["provider", "collection_name", "level"],
    "ingestion": ["provider"],
    "vector_database": ["provider", "collection_name"],
    "app": ["max_logs"],
}


class R2RConfig:
    def __init__(self, config_data: dict[str, Any]):
        for section, keys in REQUIRED_KEYS.items():
            self._validate_config_section(config_data, section, keys)
            setattr(self, section, config_data[section])

    def _validate_config_section(
        self, config_data: dict[str, Any], section: str, keys: list
    ):
        if section not in config_data:
            raise ValueError(f"Missing '{section}' section in config")
        if not all(key in config_data[section] for key in keys):
            raise ValueError(f"Missing required keys in '{section}' config")

    @classmethod
    def load_config(cls, config_path: str = None) -> "R2RConfig":
        if config_path is None:
            # Get the root directory of the project
            root_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            config_path = os.path.join(root_dir, "config.json")

        # Load configuration from JSON file
        with open(config_path) as f:
            config_data = json.load(f)

        return cls(config_data)

    # TODO - How to type 'redis.Redis' without introducing dependency on 'redis' package?
    def save_to_redis(self, redis_client: Any, key: str):
        config_data = {
            section: getattr(self, section) for section in REQUIRED_KEYS.keys()
        }
        redis_client.set(f"R2RConfig:{key}", json.dumps(config_data))

    @classmethod
    def load_from_redis(cls, redis_client: Any, key: str) -> "R2RConfig":
        config_data = redis_client.get(f"R2RConfig:{key}")
        if config_data is None:
            raise ValueError(
                f"Configuration not found in Redis with key '{key}'"
            )
        return cls(json.loads(config_data))


def apply_cors(app):
    # CORS setup
    origins = [
        "*",  # TODO - Change this to the actual frontend URL
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # Allows specified origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )


def configure_logging():
    # Determine the root directory of the project
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(
        root_dir, "..", "logs"
    )  # Place the logs directory one level above the root directory

    # Create the logs directory if it doesn't exist
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Create a custom logger
    logger = logging.getLogger("r2r")
    logger.setLevel(logging.DEBUG)  # Set the logging level

    # Create handlers (console and file handler with rotation)
    c_handler = logging.StreamHandler()
    log_file_path = os.path.join(logs_dir, "r2r.log")
    f_handler = RotatingFileHandler(
        log_file_path, maxBytes=1000000, backupCount=5
    )
    c_handler.setLevel(logging.WARNING)  # Console handler level
    f_handler.setLevel(logging.DEBUG)  # File handler level

    # Create formatters and add it to handlers
    c_format = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    f_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    c_handler.setFormatter(c_format)
    f_handler.setFormatter(f_format)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)


def update_aggregation_entries(
    log: dict[str, Any],
    event_aggregation: dict[str, dict[str, Union[str, list]]],
):
    pipeline_run_id = log["pipeline_run_id"]
    if pipeline_run_id is None:
        logger.error(f"Missing 'pipeline_run_id' in log: {log}")
        raise ValueError(f"Missing 'pipeline_run_id' in log: {log}")

    pipeline_run_type = log["pipeline_run_type"]
    if pipeline_run_type is None:
        logger.error(f"Missing 'pipeline_run_type' in log: {log}")
        raise ValueError(f"Missing 'pipeline_run_type' in log: {log}")

    if pipeline_run_id not in event_aggregation:
        event_aggregation[pipeline_run_id] = {
            "timestamp": log["timestamp"],
            "pipeline_run_id": pipeline_run_id,
            "pipeline_run_type": pipeline_run_type,
            "events": [],
        }
    event = {
        "method": log["method"],
        "result": log["result"],
        "log_level": log["log_level"],
        "outcome": "success" if log["log_level"] == "INFO" else "fail",
    }
    if (
        pipeline_run_id not in event_aggregation
        or "events" not in event_aggregation[pipeline_run_id]
    ):
        if isinstance(event_aggregation[pipeline_run_id]["events"], list):
            raise ValueError(f"Incorrect 'events' datatype event_aggregation")

        raise ValueError(
            f"Missing 'pipeline_run_id' in event_aggregation: {event_aggregation}"
        )

    event_aggregation[pipeline_run_id]["events"].append(event)  # type: ignore


def process_event(event: dict[str, Any], pipeline_type: str) -> dict[str, Any]:
    method = event["method"]
    result = event.get("result", "N/A")
    processed_result = {}

    if method == "ingress":
        try:
            processed_result["search_query"] = result
        except Exception as e:
            logger.error(f"Error {e} processing 'ingress' event: {event}")
    elif method == "ingress" and pipeline_type == "embedding":
        try:
            id_match = re.search(r"'id': '([^']+)'", result)
            text_match = re.search(r"'text': '([^']+)'", result)
            metadata_match = re.search(r"'metadata': (\{[^}]+\})", result)
            if not id_match or not text_match or not metadata_match:
                raise ValueError(
                    f"Missing 'id', 'text', or 'metadata' in result: {result}"
                )
            metadata = metadata_match.group(1).replace("'", '"')
            metadata_json = json.loads(metadata)

            processed_result["document"] = BasicDocument(
                id=id_match.group(1),
                text=text_match.group(1),
                metadata=metadata_json,
            )
        except Exception as e:
            logger.error(f"Error {e} processing 'ingress' event: {event}")
    elif method == "search":
        try:
            text_matches = re.findall(r"'text': '([^']*)'", result)
            scores = re.findall(r"score=(\d+\.\d+)", result)
            processed_result["search_results"] = [
                {"text": text, "score": score}
                for text, score in zip(text_matches, scores)
            ]
            processed_result["method"] = "Search"
        except Exception as e:
            logger.error(f"Error {e} processing 'ingress' event: {event}")

    elif method == "generate_completion":
        try:
            if "content=" in result:
                content_matches = re.findall(r'content="([^"]*)"', result)
                processed_result["completion_result"] = ", ".join(
                    content_matches
                )
            else:
                processed_result["completion_result"] = result
            processed_result["method"] = "RAG"
        except Exception as e:
            logger.error(
                f"Error {e} processing 'generate_completion' event: {event}"
            )
    elif method == "evaluate":
        try:
            result = result.replace("'", '"')  # Convert to valid JSON string
            processed_result["eval_results"] = json.loads(result)
        except Exception as e:
            logger.error(f"Error {e} decoding JSON: {e}")
    elif method == "transform_chunks":
        try:
            processed_result["method"] = "Embedding"
            processed_result["embedding_chunks"] = result
        except Exception as e:
            logger.error(
                f"Error {e} processing 'transform_chunks' event: {event}"
            )

    return processed_result


def combine_aggregated_logs(
    event_aggregation: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    logs_summary = []
    for run_id, aggregation in event_aggregation.items():
        # Assuming 'pipeline_run_type' is available in the log entries to determine the type of pipeline
        pipeline_type = (
            aggregation["pipeline_run_type"]
            if "pipeline_run_type" in aggregation
            else "unknown"
        )

        summary_entry = {
            "timestamp": aggregation["timestamp"],
            "pipeline_run_id": run_id,
            "pipeline_run_type": pipeline_type,
            "method": "",
            "search_query": "",
            "search_results": [],
            "eval_results": None,
            "embedding_chunks": None,
            "document": None,
            "completion_result": "N/A",
            "outcome": (
                "success"
                if aggregation["events"][-1].get("log_level") == "INFO"
                else "fail"
            ),
        }

        for event in aggregation["events"]:
            new_event = process_event(event, pipeline_type)
            if summary_entry["embedding_chunks"]:
                new_event["embedding_chunks"] = summary_entry[
                    "embedding_chunks"
                ] + new_event.get("embedding_chunks", "")

            if summary_entry["document"] is not None:
                new_event.pop("document", None)
            summary_entry.update(new_event)
        logs_summary.append(summary_entry)
    return logs_summary


def process_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_aggregation: dict = {}
    for log in logs:
        update_aggregation_entries(log, event_aggregation)
    # Convert each aggregated log entry to SummaryLogModel before returning
    return combine_aggregated_logs(event_aggregation)
