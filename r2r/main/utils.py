import json
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Any

logger = logging.getLogger(__name__)


# Function to find the project root by looking for a .git folder or setup.py file
def find_project_root(current_dir):
    for parent in current_dir.parents:
        if any((parent / marker).exists() for marker in [".git", "setup.py"]):
            return parent
    return current_dir  # Fallback to current dir if no marker found


def load_config(config_path=None):
    if config_path is None:
        # Get the root directory of the project
        root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        config_path = os.path.join(root_dir, "config.json")

    # Load configuration from JSON file
    with open(config_path) as f:
        config = json.load(f)

    # Extract configuration parameters
    api_config = config["api"]
    logging_config = config["logging"]
    embedding_config = config["embedding"]
    database_config = config["database"]
    llm_config = config["language_model"]
    text_splitter_config = config["text_splitter"]

    return (
        api_config,
        logging_config,
        embedding_config,
        database_config,
        llm_config,
        text_splitter_config,
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
    log: dict[str, Any], event_aggregation: dict[str, dict[str, dict]]
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
    event_aggregation[pipeline_run_id]["events"].append(event)


def process_event(event: dict[str, Any]) -> dict[str, Any]:
    method = event["method"]
    result = event.get("result", "N/A")
    processed_result = {}

    if method == "ingress":
        processed_result["search_query"] = result
    elif method == "search":
        text_matches = re.findall(r"'text': '([^']*)'", result)
        scores = re.findall(r"score=(\d+\.\d+)", result)
        processed_result["search_results"] = [
            {"text": text, "score": score}
            for text, score in zip(text_matches, scores)
        ]
        processed_result["method"] = "Search"
    elif method == "generate_completion":
        content_matches = re.findall(r"content='([^']*)'", result)
        processed_result["completion_result"] = ", ".join(content_matches)
        processed_result["method"] = "Generate Completion"

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
            # "search_score": "",
            "completion_result": "N/A",  # Default to "N/A" if not applicable
            "outcome": "success"
            if aggregation["events"][-1].get("log_level") == "INFO"
            else "fail",
        }

        for event in aggregation["events"]:
            summary_entry.update(process_event(event))
        logs_summary.append(summary_entry)
    return logs_summary


def process_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_aggregation = {}
    for log in logs:
        update_aggregation_entries(log, event_aggregation)
    # Convert each aggregated log entry to SummaryLogModel before returning
    return combine_aggregated_logs(event_aggregation)
