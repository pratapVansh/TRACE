class AuthServiceError(Exception):
    """Base class for auth service failures."""


class EmailAlreadyRegisteredError(AuthServiceError):
    """Raised when an administrator creates a user with an existing email."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when login credentials are invalid."""


class InactiveAccountError(AuthServiceError):
    """Raised when a login attempt targets a deactivated user account."""


class InvalidRefreshTokenError(AuthServiceError):
    """Raised when a refresh token is invalid, revoked, or not found."""


class RevokedRefreshTokenError(AuthServiceError):
    """Raised when a refresh token is no longer present in the database."""


class ExpiredRefreshTokenError(AuthServiceError):
    """Raised when a refresh token has expired."""


class UserNotFoundError(AuthServiceError):
    """Raised when an authenticated subject does not match a stored user."""
