import json
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Any, Union

from fastapi.middleware.cors import CORSMiddleware

from r2r.core import (
    EmbeddingConfig,
    EvalConfig,
    LLMConfig,
    PromptConfig,
    VectorDBConfig,
)

logger = logging.getLogger(__name__)


class R2RConfig:
    REQUIRED_KEYS: dict[str, list] = {
        "app": [],
        "embedding": [
            "provider",
            "search_model",
            "search_dimension",
            "batch_size",
            "text_splitter",
        ],
        "eval": [
            "provider",
            "sampling_fraction",
        ],
        "ingestion": [],
        "language_model": ["provider"],
        "logging_database": ["provider", "collection_name"],
        "prompt": ["provider"],
        "vector_database": ["provider", "collection_name"],
    }

    def __init__(self, config_data: dict[str, Any]):
        # Load the default configuration
        default_config = self.load_default_config()

        # Override the default configuration with the passed configuration
        for key in config_data:
            if key in default_config:
                default_config[key].update(config_data[key])
            else:
                default_config[key] = config_data[key]

        # Validate and set the configuration
        for section, keys in R2RConfig.REQUIRED_KEYS.items():
            self._validate_config_section(default_config, section, keys)
            setattr(self, section, default_config[section])

        self.embedding = EmbeddingConfig.create(**self.embedding)
        self.eval = EvalConfig.create(**self.eval)
        self.language_model = LLMConfig.create(**self.language_model)
        self.prompt = PromptConfig.create(**self.prompt)
        self.vector_database = VectorDBConfig.create(**self.vector_database)

    def _validate_config_section(
        self, config_data: dict[str, Any], section: str, keys: list
    ):
        if section not in config_data:
            raise ValueError(f"Missing '{section}' section in config")
        if not all(key in config_data[section] for key in keys):
            raise ValueError(f"Missing required keys in '{section}' config")

    @classmethod
    def from_json(cls, config_path: str = None) -> "R2RConfig":
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
            section: getattr(self, section)
            for section in R2RConfig.REQUIRED_KEYS.keys()
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

    @classmethod
    def load_default_config(cls) -> dict:
        # Get the root directory of the project
        root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        default_config_path = os.path.join(root_dir, "config.json")

        # Load default configuration from JSON file
        with open(default_config_path) as f:
            return json.load(f)


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
    pipe_run_id = log["pipe_run_id"]
    if pipe_run_id is None:
        logger.error(f"Missing 'pipe_run_id' in log: {log}")
        raise ValueError(f"Missing 'pipe_run_id' in log: {log}")

    pipe_run_type = log["pipe_run_type"]
    if pipe_run_type is None:
        logger.error(f"Missing 'pipe_run_type' in log: {log}")
        raise ValueError(f"Missing 'pipe_run_type' in log: {log}")

    if pipe_run_id not in event_aggregation:
        event_aggregation[pipe_run_id] = {
            "timestamp": log["timestamp"],
            "pipe_run_id": pipe_run_id,
            "pipe_run_type": pipe_run_type,
            "events": [],
        }
    event = {
        "method": log["method"],
        "result": log["result"],
        "log_level": log["log_level"],
        "outcome": "success" if log["log_level"] == "INFO" else "fail",
    }
    if (
        pipe_run_id not in event_aggregation
        or "events" not in event_aggregation[pipe_run_id]
    ):
        if isinstance(event_aggregation[pipe_run_id]["events"], list):
            raise ValueError(f"Incorrect 'events' datatype event_aggregation")

        raise ValueError(
            f"Missing 'pipe_run_id' in event_aggregation: {event_aggregation}"
        )

    event_aggregation[pipe_run_id]["events"].append(event)  # type: ignore


def process_event(event: dict[str, Any], type: str) -> dict[str, Any]:
    method = event["method"]
    result = event.get("result", "N/A")
    processed_result = {}

    if method == "ingress":
        try:
            processed_result["search_query"] = result
        except Exception as e:
            logger.error(f"Error {e} processing 'ingress' event: {event}")
    elif method == "ingress" and type == "embedding":
        try:
            id_match = re.search(r"'document_id': '([^']+)'", result)
            page_number = re.search(r"'page_number': '([^']+)'", result)
            text_match = re.search(r"'text': '([^']+)'", result)
            metadata_match = re.search(r"'metadata': (\{[^}]+\})", result)
            if not id_match or not text_match or not metadata_match:
                raise ValueError(
                    f"Missing 'id', 'text', or 'metadata' in result: {result}"
                )
            metadata = metadata_match.group(1).replace("'", '"')
            metadata_json = json.loads(metadata)

            processed_result["document"] = BaseDocument(
                document_id=id_match.group(1),
                page_number=int(page_number.group(1)),
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
    elif method == "transform_fragments":
        try:
            processed_result["method"] = "Embedding"
            processed_result["embedding_chunks"] = result
        except Exception as e:
            logger.error(
                f"Error {e} processing 'transform_fragments' event: {event}"
            )

    return processed_result


def combine_aggregated_logs(
    event_aggregation: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    logs_summary = []
    for run_id, aggregation in event_aggregation.items():
        # Assuming 'pipe_run_type' is available in the log entries to determine the type of pipe
        type = (
            aggregation["pipe_run_type"]
            if "pipe_run_type" in aggregation
            else "unknown"
        )

        summary_entry = {
            "timestamp": aggregation["timestamp"],
            "pipe_run_id": run_id,
            "pipe_run_type": type,
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
            new_event = process_event(event, type)
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
