from collections.abc import AsyncGenerator

from groq import AsyncGroq
from groq import BadRequestError as GroqBadRequestError
from groq import RateLimitError as GroqRateLimitError
from groq import APIConnectionError as GroqAPIConnectionError
from groq import AuthenticationError as GroqAuthenticationError

from app.ai.base import (
    LLMProvider,
    LLMConnectionError,
    LLMConfigurationError,
    LLMGenerationError,
)
from app.core.config import settings
from app.core.logging import logger


class GroqProvider(LLMProvider):
    """LLM provider backed by Groq's API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.groq_api_key
        self._model = model or settings.groq_model
        self._client: AsyncGroq | None = None

        if not self._api_key:
            raise LLMConfigurationError(
                "GROQ_API_KEY is not set. Provide an api_key or set the environment variable."
            )

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    async def initialize(self) -> None:
        self._client = AsyncGroq(api_key=self._api_key)
        logger.info(
            "GroqProvider created — model=%s",
            self._model,
        )

        try:
            await self._client.models.list()
            logger.info("GroqProvider connectivity verified")
        except GroqAuthenticationError as exc:
            logger.error("Authentication failed — invalid GROQ_API_KEY")
            raise LLMConfigurationError(
                "Groq authentication failed — check GROQ_API_KEY"
            ) from exc
        except GroqAPIConnectionError as exc:
            logger.error("Cannot reach Groq API — %s", exc)
            raise LLMConnectionError(
                "Cannot reach Groq API — check network connectivity"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during Groq initialization")
            raise LLMConnectionError(
                f"Groq API health check failed: {exc}"
            ) from exc

    async def health_check(self) -> dict:
        if self._client is None:
            logger.warning("Health check skipped — GroqProvider not initialized")
            return {
                "connected": False,
                "provider": self.provider_name,
                "model": self._model,
            }

        try:
            await self._client.models.list()
            logger.info(
                "Health check passed — provider=%s model=%s",
                self.provider_name,
                self._model,
            )
            return {
                "connected": True,
                "provider": self.provider_name,
                "model": self._model,
            }
        except GroqAPIConnectionError as exc:
            logger.error("Health check failed — connection error: %s", exc)
            return {
                "connected": False,
                "provider": self.provider_name,
                "model": self._model,
            }
        except Exception as exc:
            logger.error("Health check failed — %s: %s", type(exc).__name__, exc)
            return {
                "connected": False,
                "provider": self.provider_name,
                "model": self._model,
            }

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        if self._client is None:
            raise LLMConfigurationError("GroqProvider not initialized — call initialize() first")

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = kwargs.pop("model", self._model)
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
        except GroqRateLimitError as exc:
            logger.warning("Rate limit exceeded for model=%s: %s", model, exc)
            raise LLMGenerationError(f"Groq rate limit exceeded: {exc}") from exc
        except GroqBadRequestError as exc:
            logger.error("Bad request for model=%s: %s", model, exc)
            raise LLMGenerationError(f"Groq bad request: {exc}") from exc
        except GroqAPIConnectionError as exc:
            logger.error("Connection lost for model=%s: %s", model, exc)
            raise LLMConnectionError(f"Groq connection lost: {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected error during generation for model=%s", model)
            raise LLMGenerationError(f"Groq generation failed: {exc}") from exc

        content = response.choices[0].message.content
        if content is None:
            logger.error("Groq returned empty response for model=%s", model)
            raise LLMGenerationError("Groq returned an empty response")
        return content

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        if self._client is None:
            raise LLMConfigurationError("GroqProvider not initialized — call initialize() first")

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = kwargs.pop("model", self._model)
        try:
            stream = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None)
                if token:
                    yield token
        except GroqRateLimitError as exc:
            logger.warning("Rate limit exceeded during stream for model=%s: %s", model, exc)
            raise LLMGenerationError(f"Groq rate limit exceeded: {exc}") from exc
        except GroqBadRequestError as exc:
            logger.error("Bad request during stream for model=%s: %s", model, exc)
            raise LLMGenerationError(f"Groq bad request: {exc}") from exc
        except GroqAPIConnectionError as exc:
            logger.error("Connection lost during stream for model=%s: %s", model, exc)
            raise LLMConnectionError(f"Groq connection lost: {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected error during streaming for model=%s", model)
            raise LLMGenerationError(f"Groq streaming failed: {exc}") from exc
