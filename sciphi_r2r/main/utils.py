import logging
import os
from logging.handlers import RotatingFileHandler


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
    logger = logging.getLogger("sciphi_r2r")
    logger.setLevel(logging.DEBUG)  # Set the logging level

    # Create handlers (console and file handler with rotation)
    c_handler = logging.StreamHandler()
    log_file_path = os.path.join(logs_dir, "sciphi_r2r.log")
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
