class TokenError(Exception):
    """Base class for JWT validation failures."""


class TokenExpiredError(TokenError):
    """Raised when a token signature is valid but the token has expired."""


class InvalidTokenError(TokenError):
    """Raised when a token is malformed, has an invalid signature, or wrong type."""
