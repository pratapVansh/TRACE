from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class LLMError(Exception):
    """Base class for LLM provider failures."""


class LLMConnectionError(LLMError):
    """Raised when the LLM provider cannot be reached."""


class LLMConfigurationError(LLMError):
    """Raised when the LLM provider is misconfigured."""


class LLMGenerationError(LLMError):
    """Raised when a generation request fails."""


class LLMProvider(ABC):
    """Abstract interface for an LLM backend."""

    @abstractmethod
    async def initialize(self) -> None:
        """Create the client and verify the service is reachable."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Return a dictionary with provider, model, and connection status."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        """Generate a completion for the given prompt."""
        ...

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming completion. Yields tokens as they arrive."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the human-readable provider name (e.g. 'groq')."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier being used."""
