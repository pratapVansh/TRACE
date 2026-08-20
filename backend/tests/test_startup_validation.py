"""Tests for fail-fast security configuration validation.

Regression cover for the fail-open JWT secret: ``Settings.jwt_secret_key``
defaults to ``""`` and ``get_jwt_secret_key`` returns that default when
Vault is disabled, so an unset ``JWT_SECRET_KEY`` meant every token was
signed and verified with an empty HMAC key.
"""

import pytest

from app.core.security.startup_validation import (
    InsecureConfigurationError,
    validate_jwt_secret,
    validate_security_configuration,
)

STRONG_SECRET = "9f2c" * 16  # 64 chars


class _FakeSettings:
    def __init__(self, secret: str, debug: bool = False) -> None:
        self._secret = secret
        self.debug = debug

    @property
    def get_jwt_secret_key(self) -> str:
        return self._secret


class TestEmptySecretIsAlwaysFatal:
    """An empty signing key is the fail-open case — never allow it."""

    @pytest.mark.parametrize("secret", ["", "   ", "\t\n", None])
    @pytest.mark.parametrize("debug", [False, True])
    def test_empty_secret_rejected(self, secret, debug):
        with pytest.raises(InsecureConfigurationError, match="not set"):
            validate_jwt_secret(secret, debug=debug)

    def test_error_names_the_offending_variable(self):
        with pytest.raises(InsecureConfigurationError, match="JWT_SECRET_KEY"):
            validate_jwt_secret("", debug=False)


class TestWeakSecrets:
    @pytest.mark.parametrize(
        "secret",
        ["change-me-in-production", "changeme", "secret", "your-secret-key-here"],
    )
    def test_placeholder_rejected_outside_debug(self, secret):
        with pytest.raises(InsecureConfigurationError, match="placeholder"):
            validate_jwt_secret(secret, debug=False)

    def test_placeholder_is_case_insensitive(self):
        with pytest.raises(InsecureConfigurationError, match="placeholder"):
            validate_jwt_secret("Change-Me-In-Production", debug=False)

    def test_short_secret_rejected_outside_debug(self):
        with pytest.raises(InsecureConfigurationError, match="characters"):
            validate_jwt_secret("a" * 31, debug=False)

    def test_boundary_length_accepted(self):
        validate_jwt_secret("a" * 32, debug=False)

    def test_weak_secret_allowed_in_debug_with_warning(self, caplog):
        """Local dev against a copied .env.example must still run, but loudly."""
        with caplog.at_level("WARNING"):
            validate_jwt_secret("change-me-in-production", debug=True)
        assert "INSECURE JWT CONFIGURATION" in caplog.text


class TestValidateSecurityConfiguration:
    def test_accepts_strong_secret(self):
        validate_security_configuration(_FakeSettings(STRONG_SECRET))

    def test_rejects_empty_secret(self):
        with pytest.raises(InsecureConfigurationError):
            validate_security_configuration(_FakeSettings(""))

    def test_debug_does_not_bypass_empty_secret(self):
        with pytest.raises(InsecureConfigurationError):
            validate_security_configuration(_FakeSettings("", debug=True))
