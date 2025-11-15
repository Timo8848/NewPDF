from __future__ import annotations

import logging
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Iterator

import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
    )


def get_logger(name: str = __name__):
    return structlog.get_logger(name)


@contextmanager
def traced(name: str) -> Iterator[dict]:
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    logger = get_logger("tracer").bind(trace_id=trace_id, span=name)
    logger.info("start")
    try:
        yield {"trace_id": trace_id}
    except Exception as exc:
        logger.exception("error", error=str(exc))
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("end", elapsed_ms=elapsed_ms)
