"""Fail-fast validation of security-critical configuration.

``Settings.jwt_secret_key`` defaults to ``""`` and ``get_jwt_secret_key``
falls back to that default whenever Vault is disabled or unreachable
(``VaultClient.enabled`` is ``False`` without ``VAULT_TOKEN``).  Nothing
rejected the empty value, so a misconfigured deployment would sign and
*verify* every JWT with an empty HMAC key — anyone could mint valid
tokens for any user id and role.

These checks run at application startup so the process refuses to serve
traffic rather than failing open.
"""

import logging

logger = logging.getLogger(__name__)

# Minimum length for an HS256 secret. HMAC-SHA256 has a 256-bit block, so
# anything shorter than 32 characters provides less entropy than the
# algorithm assumes.
MIN_JWT_SECRET_LENGTH = 32

# Values shipped in .env.example / common tutorials. These are public, so
# treating them as secrets is equivalent to having no secret at all.
PLACEHOLDER_JWT_SECRETS = frozenset(
    {
        "change-me-in-production",
        "changeme",
        "change-me",
        "your-secret-key-here",
        "your-secret-key",
        "secret",
        "supersecret",
        "test",
    }
)


class InsecureConfigurationError(RuntimeError):
    """Raised when security-critical settings are missing or unsafe."""


def validate_jwt_secret(secret: str | None, *, debug: bool = False) -> None:
    """Validate the resolved JWT signing secret.

    An empty secret is always fatal — it is the fail-open case that makes
    token forgery trivial. Placeholder or short secrets are fatal outside
    debug mode, and downgraded to a loud warning in debug so that local
    development against a copied ``.env.example`` still runs.

    Args:
        secret: The resolved signing secret (``settings.get_jwt_secret_key``).
        debug: Whether the app is running in debug mode.

    Raises:
        InsecureConfigurationError: If the secret is unusable.
    """
    if secret is None or not secret.strip():
        raise InsecureConfigurationError(
            "JWT_SECRET_KEY is not set. Tokens would be signed with an empty "
            "key, allowing anyone to forge credentials for any user. Set "
            "JWT_SECRET_KEY in your .env (generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\")."
        )

    problems: list[str] = []
    if secret.strip().lower() in PLACEHOLDER_JWT_SECRETS:
        problems.append(
            "JWT_SECRET_KEY is a well-known placeholder value and provides no security"
        )
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        problems.append(
            f"JWT_SECRET_KEY is only {len(secret)} characters; "
            f"at least {MIN_JWT_SECRET_LENGTH} are required for HS256"
        )

    if not problems:
        return

    detail = "; ".join(problems)
    if debug:
        # Never silently accept a weak secret — make it impossible to miss.
        logger.warning(
            "INSECURE JWT CONFIGURATION (allowed because debug=True): %s. "
            "This MUST be fixed before deploying.",
            detail,
        )
        return

    raise InsecureConfigurationError(
        f"{detail}. Set a strong JWT_SECRET_KEY (generate one with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\"), "
        "or set DEBUG=true to allow it for local development only."
    )


def validate_security_configuration(settings) -> None:
    """Run every startup security check. Call this before serving traffic."""
    validate_jwt_secret(settings.get_jwt_secret_key, debug=settings.debug)
