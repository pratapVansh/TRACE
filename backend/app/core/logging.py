import json
import logging
import os
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

from app.core.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDFilter(logging.Filter):
    """Inject the current request correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        })


_handlers: list[logging.Handler] = []

_stream = logging.StreamHandler()
_stream.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(request_id)s | %(message)s",
    ),
)
_stream.addFilter(RequestIDFilter())
_handlers.append(_stream)

_log_dir = os.environ.get("TRACE_LOG_DIR", "")
if _log_dir:
    os.makedirs(_log_dir, exist_ok=True)
    log_path = os.path.join(_log_dir, "trace.log")
    _file = RotatingFileHandler(log_path, maxBytes=50 * 1024 * 1024, backupCount=5, encoding="utf-8")
    if os.environ.get("TRACE_LOG_FORMAT", "").lower() == "json":
        _file.setFormatter(JSONFormatter())
    else:
        _file.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(request_id)s | %(message)s",
            ),
        )
    _file.addFilter(RequestIDFilter())
    _handlers.append(_file)
    logging.info("File logging enabled at %s (format=%s)", log_path,
                 os.environ.get("TRACE_LOG_FORMAT", "text"))

_root = logging.getLogger()
_root.setLevel(logging.INFO)
for existing_handler in list(_root.handlers):
    _root.removeHandler(existing_handler)
for h in _handlers:
    _root.addHandler(h)

logger = logging.getLogger("trace")
