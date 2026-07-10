import logging
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDFilter(logging.Filter):
    """Inject the current request correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


_handler = logging.StreamHandler()
_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(request_id)s | %(message)s",
    ),
)
_handler.addFilter(RequestIDFilter())

_root = logging.getLogger()
_root.setLevel(logging.INFO)
for existing_handler in list(_root.handlers):
    _root.removeHandler(existing_handler)
_root.addHandler(_handler)

logger = logging.getLogger("trace")
