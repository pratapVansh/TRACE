"""Tests for LLM configuration validation and GroqProvider initialization."""

import pytest

from app.ai.base import LLMConfigurationError
from app.ai.groq_provider import GroqProvider
from app.core.config import settings


@pytest.fixture
def no_configured_api_key(monkeypatch):
    """Isolate from a real GROQ_API_KEY in the developer's .env.

    ``GroqProvider`` falls back to ``settings.groq_api_key`` when no key is
    passed, so these tests only exercise the missing-key path if the
    configured value is empty too.
    """
    monkeypatch.setattr(settings, "groq_api_key", "")


class TestGroqProviderInit:
    def test_missing_api_key_raises(self, no_configured_api_key):
        with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
            GroqProvider(api_key=None)

    def test_empty_api_key_raises(self, no_configured_api_key):
        with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
            GroqProvider(api_key="")

    def test_falls_back_to_configured_api_key(self, monkeypatch):
        monkeypatch.setattr(settings, "groq_api_key", "sk-from-settings")
        assert GroqProvider(api_key=None).provider_name == "groq"

    def test_valid_api_key_creates_provider(self):
        provider = GroqProvider(api_key="sk-test-key", model="llama-3.3-70b-versatile")
        assert provider.provider_name == "groq"
        assert provider.model_name == "llama-3.3-70b-versatile"

    async def test_not_initialized_raises_on_generate(self):
        provider = GroqProvider(api_key="sk-test-key")
        with pytest.raises(LLMConfigurationError, match="not initialized"):
            await provider.generate("test prompt")

    async def test_not_initialized_raises_on_stream(self):
        provider = GroqProvider(api_key="sk-test-key")
        with pytest.raises(LLMConfigurationError, match="not initialized"):
            async for _ in provider.stream_generate("test prompt"):
                pass


class TestGroqProviderProperties:
    def test_provider_name(self):
        p = GroqProvider(api_key="sk-test")
        assert p.provider_name == "groq"

    def test_model_name_defaults_to_configured_model(self, monkeypatch):
        """With no explicit model, the configured GROQ_MODEL is used.

        Asserted against ``settings.groq_model`` rather than a hardcoded
        name so changing GROQ_MODEL in .env does not fail the suite.
        """
        monkeypatch.setattr(settings, "groq_model", "configured-model-x")
        assert GroqProvider(api_key="sk-test").model_name == "configured-model-x"

    def test_model_name_custom(self):
        p = GroqProvider(api_key="sk-test", model="mixtral-8x7b-32768")
        assert p.model_name == "mixtral-8x7b-32768"
