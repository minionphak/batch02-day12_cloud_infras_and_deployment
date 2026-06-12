"""Structured JSON logging utilities.

Every log line is a single JSON object so log aggregators (Loki, Datadog,
CloudWatch) can parse fields without regex. Secrets and full question text
are never logged.
"""

import json
import logging
import sys
from datetime import datetime, timezone


def setup_logging(level: str) -> None:
    """Configure the root logger to emit plain messages at the given level.

    Args:
        level: Logging level string (e.g., 'INFO', 'DEBUG').
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def log_event(logger: logging.Logger, level: str, event: str, **fields) -> None:
    """Emit a structured JSON log line for the given event.

    Args:
        logger: Logger instance to use.
        level: Log level as string ('debug', 'info', 'warning', 'error').
        event: Event name string.
        **fields: Additional key-value pairs to include in the JSON output.
    """
    log_entry = {
        "event": event,
        "time": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(json.dumps(log_entry))
