import logging
import logging.config
import os
import re
import sys
from pathlib import Path


class HTTPStatusFilter(logging.Filter):
    """This filter inspects uvicorn.access log records. It uses
    record.getMessage() to retrieve the fully formatted log message. Then it
    searches for HTTP status codes and adjusts the.

    record's log level based on that status:
      - 4xx: WARNING
      - 5xx: ERROR
    All other logs remain unchanged.
    """

    # A broad pattern to find any 3-digit number in the message.
    # This should capture the HTTP status code from a line like:
    # '127.0.0.1:54946 - "GET /v2/relationships HTTP/1.1" 404'
    STATUS_CODE_PATTERN = re.compile(r"\b(\d{3})\b")
    HEALTH_ENDPOINT_PATTERN = re.compile(r'"GET /v3/health HTTP/\d\.\d"')

    LEVEL_TO_ANSI = {
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
    }
    RESET = "\033[0m"

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "uvicorn.access":
            return True

        message = record.getMessage()

        # Filter out health endpoint requests
        # FIXME: This should be made configurable in the future
        if self.HEALTH_ENDPOINT_PATTERN.search(message):
            return False

        if codes := self.STATUS_CODE_PATTERN.findall(message):
            status_code = int(codes[-1])
            if 200 <= status_code < 300:
                record.levelno = logging.INFO
                record.levelname = "INFO"
                color = self.LEVEL_TO_ANSI[logging.INFO]
            elif 400 <= status_code < 500:
                record.levelno = logging.WARNING
                record.levelname = "WARNING"
                color = self.LEVEL_TO_ANSI[logging.WARNING]
            elif 500 <= status_code < 600:
                record.levelno = logging.ERROR
                record.levelname = "ERROR"
                color = self.LEVEL_TO_ANSI[logging.ERROR]
            else:
                return True

            # Wrap the status code in ANSI codes
            colored_code = f"{color}{status_code}{self.RESET}"
            # Replace the status code in the message
            new_msg = message.replace(str(status_code), colored_code)

            # Update record.msg and clear args to avoid formatting issues
            record.msg = new_msg
            record.args = ()

        return True


log_level = os.environ.get("R2R_LOG_LEVEL", "INFO").upper()
log_console_formatter = os.environ.get(
    "R2R_LOG_CONSOLE_FORMATTER", "colored"
).lower()  # colored or json

log_dir = Path.cwd() / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "app.log"

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "http_status_filter": {
            "()": HTTPStatusFilter,
        }
    },
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "colored": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(asctime)s - %(log_color)s%(levelname)s%(reset)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "log_colors": {
                "DEBUG": "white",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        },
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(name)s %(levelname)s %(message)s",  # these become keys in the JSON log
            "rename_fields": {
                "asctime": "time",
                "levelname": "level",
                "name": "logger",
            },
        },
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "colored",
            "filename": log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "filters": ["http_status_filter"],
            "level": log_level,  # Set handler level based on the environment variable
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": log_console_formatter,
            "stream": sys.stdout,
            "filters": ["http_status_filter"],
            "level": log_level,  # Set handler level based on the environment variable
        },
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file"],
            "level": log_level,  # Set logger level based on the environment variable
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": log_level,
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["console", "file"],
            "level": log_level,
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["console", "file"],
            "level": log_level,
            "propagate": False,
        },
    },
}


def configure_logging() -> Path:
    logging.config.dictConfig(log_config)

    logging.info(f"Logging is configured at {log_level} level.")

    return log_file
