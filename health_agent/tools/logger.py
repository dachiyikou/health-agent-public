from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

from health_agent.config import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LOG_FILE_PATH


def build_logger(name: str = "health_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(logging.StreamHandler())
    return logger


class TraceLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def ping_langfuse(self) -> None:
        if not LANGFUSE_HOST:
            self.logger.warning("LANGFUSE_HOST is empty; LangFuse tracing disabled.")
            return
        if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
            self.logger.warning("LangFuse keys are not configured; trace export disabled.")
            return
        response = requests.get(LANGFUSE_HOST, timeout=5)
        response.raise_for_status()

    def log_event(self, event: str, payload: dict[str, Any]) -> None:
        self.logger.info("%s | %s", event, payload)
