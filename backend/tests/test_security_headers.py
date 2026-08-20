"""Tests for security response headers.

The CSP ``connect-src`` directive was hardcoded to ``http://localhost:3000``
and ``http://localhost:8000``, which silently breaks any deployment that
is not on localhost. It is now derived from ``BACKEND_CORS_ORIGINS``.
"""

from unittest.mock import patch

from app.middleware.security_headers import _build_connect_src


class _FakeSettings:
    def __init__(self, origins: list[str]) -> None:
        self.cors_origins = origins


def _connect_src_for(origins: list[str]) -> str:
    with patch(
        "app.middleware.security_headers.settings", _FakeSettings(origins)
    ):
        return _build_connect_src()


class TestConnectSrc:
    def test_always_includes_self(self):
        assert _connect_src_for([]) == "'self'"

    def test_includes_configured_origin(self):
        assert _connect_src_for(["http://localhost:3000"]) == (
            "'self' http://localhost:3000"
        )

    def test_follows_non_localhost_origins(self):
        """The regression: production origins must appear in the CSP."""
        result = _connect_src_for(["https://trace.example.com"])
        assert "https://trace.example.com" in result
        assert "localhost" not in result

    def test_supports_multiple_origins(self):
        result = _connect_src_for(
            ["https://a.example.com", "https://b.example.com"]
        )
        assert result == "'self' https://a.example.com https://b.example.com"

    def test_deduplicates_origins(self):
        result = _connect_src_for(["https://a.example.com", "https://a.example.com"])
        assert result == "'self' https://a.example.com"

    def test_wildcard_origin_is_not_emitted(self):
        """A wildcard connect-src would defeat the point of the directive."""
        assert "*" not in _connect_src_for(["*"])

    def test_empty_entries_ignored(self):
        assert _connect_src_for(["", "https://a.example.com"]) == (
            "'self' https://a.example.com"
        )
