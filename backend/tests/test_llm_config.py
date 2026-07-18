"""Tests for LLM configuration validation and GroqProvider initialization."""

import pytest

from app.ai.base import LLMConfigurationError
from app.ai.groq_provider import GroqProvider


class TestGroqProviderInit:
    def test_missing_api_key_raises(self):
        with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
            GroqProvider(api_key=None)

    def test_empty_api_key_raises(self):
        with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
            GroqProvider(api_key="")

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

    def test_model_name_default(self):
        p = GroqProvider(api_key="sk-test")
        assert p.model_name == "llama-3.3-70b-versatile"

    def test_model_name_custom(self):
        p = GroqProvider(api_key="sk-test", model="mixtral-8x7b-32768")
        assert p.model_name == "mixtral-8x7b-32768"
