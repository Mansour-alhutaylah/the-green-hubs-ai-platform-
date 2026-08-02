"""Centralized logging configuration."""

import logging
from typing import Any

from app.core.request_context import request_context_log_fields

_REQUEST_CONTEXT_FACTORY_MARKER = "_green_hubs_request_context_aware"


def install_request_context_logging() -> None:
    """Add safe request identifiers to every log record, idempotently."""

    previous_factory = logging.getLogRecordFactory()
    if getattr(previous_factory, _REQUEST_CONTEXT_FACTORY_MARKER, False):
        return

    def context_record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous_factory(*args, **kwargs)
        for name, value in request_context_log_fields().items():
            setattr(record, name, value)
        return record

    setattr(context_record_factory, _REQUEST_CONTEXT_FACTORY_MARKER, True)
    logging.setLogRecordFactory(context_record_factory)


def configure_logging(level: str = "INFO") -> None:
    install_request_context_logging()
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s | %(levelname)-8s | %(name)s | "
            "cid=%(correlation_id)s user=%(user_id)s org=%(organization_id)s | %(message)s"
        ),
    )
