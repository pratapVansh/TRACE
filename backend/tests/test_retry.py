"""Tests for retry logic across external AI services."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from unittest.mock import ANY

from app.ai.base import LLMGenerationError
from app.ai.groq_provider import GroqProvider, _groq_retry_policy, _is_groq_retryable
from app.core.retry import RetryPolicy, async_retry, is_http_status_retryable, retry_sync
from app.services.vector_store import _is_qdrant_retryable, _qdrant_retry_policy

# ══════════════════════════════════════════════════════════════════════
# Retry utility unit tests
# ══════════════════════════════════════════════════════════════════════


class TestIsHttpStatusRetryable:
    def test_none_status_is_retryable(self):
        assert is_http_status_retryable(None) is True

    def test_5xx_is_retryable(self):
        assert is_http_status_retryable(500) is True
        assert is_http_status_retryable(502) is True
        assert is_http_status_retryable(503) is True
        assert is_http_status_retryable(504) is True

    def test_429_is_retryable(self):
        assert is_http_status_retryable(429) is True

    def test_4xx_is_not_retryable(self):
        assert is_http_status_retryable(400) is False
        assert is_http_status_retryable(401) is False
        assert is_http_status_retryable(403) is False
        assert is_http_status_retryable(404) is False
        assert is_http_status_retryable(422) is False


class TestAsyncRetry:
    async def test_succeeds_on_first_attempt(self):
        call_count = 0

        async def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await async_retry(
            succeed,
            RetryPolicy(max_retries=3, base_delay_seconds=0.01),
        )
        assert result == "ok"
        assert call_count == 1

    async def test_retries_on_failure_then_succeeds(self):
        call_count = 0

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("transient")
            return "ok"

        result = await async_retry(
            fail_twice,
            RetryPolicy(max_retries=3, base_delay_seconds=0.01),
        )
        assert result == "ok"
        assert call_count == 3

    async def test_exhausts_retries_and_raises(self):
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("always fails")

        with pytest.raises(ConnectionError):
            await async_retry(
                always_fail,
                RetryPolicy(max_retries=3, base_delay_seconds=0.01),
            )
        assert call_count == 3

    async def test_non_retryable_error_does_not_retry(self):
        call_count = 0

        async def fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad request")

        with pytest.raises(ValueError):
            await async_retry(
                fail,
                RetryPolicy(max_retries=3, base_delay_seconds=0.01),
                is_retryable=lambda exc: not isinstance(exc, ValueError),
            )
        assert call_count == 1

    async def test_exponential_backoff_increases_delay(self):
        delays: list[float] = []

        original_sleep = asyncio.sleep

        async def tracking_sleep(delay):
            delays.append(delay)
            await original_sleep(0)

        with patch("asyncio.sleep", tracking_sleep):
            call_count = 0

            async def fail_thrice():
                nonlocal call_count
                call_count += 1
                raise ConnectionError("fail")

            with pytest.raises(ConnectionError):
                await async_retry(
                    fail_thrice,
                    RetryPolicy(
                        max_retries=3,
                        base_delay_seconds=1.0,
                        max_delay_seconds=30.0,
                        enable_jitter=False,
                    ),
                )

            assert call_count == 3
            assert len(delays) == 2  # 2 retry sleeps between 3 attempts
            assert delays[0] == pytest.approx(1.0, rel=0.5)  # 2^0 * 1.0
            assert delays[1] == pytest.approx(2.0, rel=0.5)  # 2^1 * 1.0

    async def test_max_delay_caps_backoff(self):
        delays: list[float] = []

        original_sleep = asyncio.sleep

        async def tracking_sleep(delay):
            delays.append(delay)
            await original_sleep(0)

        with patch("asyncio.sleep", tracking_sleep):
            call_count = 0

            async def fail():
                nonlocal call_count
                call_count += 1
                raise ConnectionError("fail")

            policy = RetryPolicy(
                max_retries=3,
                base_delay_seconds=1.0,
                max_delay_seconds=2.0,  # cap at 2s
                enable_jitter=False,
            )

            with pytest.raises(ConnectionError):
                await async_retry(fail, policy)

            assert all(d <= 2.0 for d in delays)


class TestRetrySync:
    def test_succeeds_on_first_attempt(self):
        call_count = 0

        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = retry_sync(
            succeed,
            RetryPolicy(max_retries=3, base_delay_seconds=0.01),
        )
        assert result == "ok"
        assert call_count == 1

    def test_retries_then_succeeds(self):
        call_count = 0

        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("transient")
            return "ok"

        result = retry_sync(
            fail_twice,
            RetryPolicy(max_retries=3, base_delay_seconds=0.01),
        )
        assert result == "ok"
        assert call_count == 3

    def test_exhausts_and_raises(self):
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("always")

        with pytest.raises(ConnectionError):
            retry_sync(
                always_fail,
                RetryPolicy(max_retries=3, base_delay_seconds=0.01),
            )
        assert call_count == 3

    def test_non_retryable_does_not_retry(self):
        call_count = 0

        def fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad")

        with pytest.raises(ValueError):
            retry_sync(
                fail,
                RetryPolicy(max_retries=3, base_delay_seconds=0.01),
                is_retryable=lambda exc: not isinstance(exc, ValueError),
            )
        assert call_count == 1


# ══════════════════════════════════════════════════════════════════════
# Groq retry classification tests
# ══════════════════════════════════════════════════════════════════════


class TestGroqRetryableErrors:
    def test_bad_request_not_retryable(self):
        from groq import BadRequestError
        exc = BadRequestError("bad request", response=MagicMock(status_code=400), body=None)
        assert _is_groq_retryable(exc) is False

    def test_authentication_not_retryable(self):
        from groq import AuthenticationError
        exc = AuthenticationError("auth failed", response=MagicMock(status_code=401), body=None)
        assert _is_groq_retryable(exc) is False

    def test_rate_limit_is_retryable(self):
        from groq import RateLimitError
        exc = RateLimitError("rate limited", response=MagicMock(status_code=429), body=None)
        assert _is_groq_retryable(exc) is True

    def test_connection_error_is_retryable(self):
        from groq import APIConnectionError
        exc = APIConnectionError(message="connection lost", request=MagicMock())
        assert _is_groq_retryable(exc) is True

    def test_500_is_retryable(self):
        from groq import APIStatusError
        exc = APIStatusError("server error", response=MagicMock(status_code=500), body=None)
        assert _is_groq_retryable(exc) is True

    def test_unknown_exception_is_retryable(self):
        exc = RuntimeError("unexpected")
        assert _is_groq_retryable(exc) is True


class TestGroqProviderWithRetry:
    async def test_retries_on_connection_error_then_succeeds(self):
        from groq import APIConnectionError

        mock_client = MagicMock()
        mock_chat = MagicMock()
        mock_completions = MagicMock()

        call_count = [0]

        async def mock_create(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise APIConnectionError("transient")
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "final answer"
            return mock_response

        mock_completions.create = mock_create
        mock_chat.completions = mock_completions
        mock_client.chat = mock_chat

        provider = GroqProvider(api_key="sk-test")
        provider._client = mock_client

        result = await provider.generate("test prompt")
        assert result == "final answer"
        assert call_count[0] == 3

    async def test_does_not_retry_on_bad_request(self):
        from groq import BadRequestError

        mock_client = MagicMock()
        mock_completions = MagicMock()

        async def mock_create(**kwargs):
            raise BadRequestError("bad", response=MagicMock(status_code=400), body=None)

        mock_completions.create = mock_create
        mock_client.chat.completions = mock_completions

        provider = GroqProvider(api_key="sk-test")
        provider._client = mock_client

        with pytest.raises(LLMGenerationError, match="bad request"):
            await provider.generate("test prompt")

    async def test_retry_policy_config(self):
        assert _groq_retry_policy.max_retries == 3
        assert _groq_retry_policy.base_delay_seconds == 1.0
        assert _groq_retry_policy.max_delay_seconds == 30.0


# ══════════════════════════════════════════════════════════════════════
# Qdrant retry classification tests
# ══════════════════════════════════════════════════════════════════════


class TestQdrantRetryableErrors:
    def test_value_error_not_retryable(self):
        assert _is_qdrant_retryable(ValueError("bad param")) is False

    def test_500_is_retryable(self):
        from qdrant_client.http.exceptions import UnexpectedResponse
        exc = UnexpectedResponse(500, "Server Error", b"", {})
        assert _is_qdrant_retryable(exc) is True

    def test_429_is_retryable(self):
        from qdrant_client.http.exceptions import UnexpectedResponse
        exc = UnexpectedResponse(429, "Too Many Requests", b"", {})
        assert _is_qdrant_retryable(exc) is True

    def test_400_not_retryable(self):
        from qdrant_client.http.exceptions import UnexpectedResponse
        exc = UnexpectedResponse(400, "Bad Request", b"", {})
        assert _is_qdrant_retryable(exc) is False

    def test_connection_error_is_retryable(self):
        assert _is_qdrant_retryable(ConnectionError("refused")) is True

    def test_retry_policy_config(self):
        assert _qdrant_retry_policy.max_retries == 3
        assert _qdrant_retry_policy.base_delay_seconds == 1.0
        assert _qdrant_retry_policy.max_delay_seconds == 30.0


class TestQdrantVectorStoreWithRetry:
    async def test_retry_on_connection_error_then_succeeds(self):
        from qdrant_client.http.exceptions import UnexpectedResponse

        mock_client = MagicMock()
        call_count = [0]

        def mock_get_collections():
            call_count[0] += 1
            if call_count[0] <= 2:
                exc = UnexpectedResponse(503, headers={}, body=MagicMock())
                exc.status_code = 503
                raise exc
            return MagicMock(collections=[])

        mock_client.get_collections = mock_get_collections

        with patch("app.services.vector_store._get_client", return_value=mock_client):
            from app.services.vector_store import QdrantVectorStore
            store = QdrantVectorStore()

            await store.connect()

        assert call_count[0] == 3

    async def test_does_not_retry_on_bad_request(self):
        from qdrant_client.http.exceptions import UnexpectedResponse

        mock_client = MagicMock()
        mock_client.get_collections.side_effect = UnexpectedResponse(400, "Bad Request", b"", {})

        with patch("app.services.vector_store._get_client", return_value=mock_client):
            from app.services.vector_store import QdrantVectorStore
            store = QdrantVectorStore()

            with pytest.raises(Exception):
                await store.connect()

        assert mock_client.get_collections.call_count == 1
