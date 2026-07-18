import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

from app.core.logging import logger

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    enable_jitter: bool = True


def is_http_status_retryable(status_code: int | None) -> bool:
    if status_code is None:
        return True
    if status_code >= 500:
        return True
    if status_code == 429:
        return True
    return False


def _compute_delay(attempt: int, policy: RetryPolicy) -> float:
    delay = min(
        policy.base_delay_seconds * (2 ** (attempt - 1)),
        policy.max_delay_seconds,
    )
    if policy.enable_jitter:
        delay *= 1 + random.uniform(-0.25, 0.25)
    return delay


async def async_retry(
    coro_factory: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    is_retryable: Callable[[Exception], bool] = lambda _: True,
    operation_name: str = "operation",
) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, policy.max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if not is_retryable(exc) or attempt == policy.max_retries:
                raise
            delay = _compute_delay(attempt, policy)
            logger.warning(
                "%s attempt %d/%d failed, retrying in %.1fs: %s",
                operation_name,
                attempt,
                policy.max_retries,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    raise last_exc


def retry_sync(
    fn: Callable[..., T],
    policy: RetryPolicy,
    is_retryable: Callable[[Exception], bool] = lambda _: True,
    operation_name: str = "operation",
    *args,
    **kwargs,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, policy.max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if not is_retryable(exc) or attempt == policy.max_retries:
                raise
            delay = _compute_delay(attempt, policy)
            logger.warning(
                "%s attempt %d/%d failed, retrying in %.1fs: %s",
                operation_name,
                attempt,
                policy.max_retries,
                delay,
                exc,
            )
            import time as sync_time
            sync_time.sleep(delay)
    raise last_exc
