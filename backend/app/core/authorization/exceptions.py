from app.core.authorization.permissions import Permission


class AuthorizationError(Exception):
    """Base class for authorization failures."""


class PermissionDeniedError(AuthorizationError):
    """Raised when a role lacks a required permission."""

    def __init__(self, role: str, permission: Permission) -> None:
        self.role = role
        self.permission = permission
        super().__init__(
            f"Role '{role}' does not have permission '{permission.value}'",
        )


class UnknownRoleError(AuthorizationError):
    """Raised when a role name is not recognized by the authorization system."""

    def __init__(self, role: str) -> None:
        self.role = role
        super().__init__(f"Unknown role: '{role}'")
