class AuthServiceError(Exception):
    """Base class for auth service failures."""


class EmailAlreadyRegisteredError(AuthServiceError):
    """Raised when registration is attempted with an existing email."""


class DefaultRoleNotFoundError(AuthServiceError):
    """Raised when the default Viewer role is missing from the database."""


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
