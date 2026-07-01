class UserManagementError(Exception):
    """Base class for user management failures."""


class ManagedUserNotFoundError(UserManagementError):
    """Raised when a managed user id does not exist."""


class RoleNotFoundError(UserManagementError):
    """Raised when a requested role name is not in the database."""

    def __init__(self, role: str) -> None:
        self.role = role
        super().__init__(f"Role not found: '{role}'")


class InvalidRoleAssignmentError(UserManagementError):
    """Raised when an actor attempts to assign a role they cannot grant."""


class ForbiddenUserManagementActionError(UserManagementError):
    """Raised when an actor cannot modify the target user."""


class SelfModificationForbiddenError(UserManagementError):
    """Raised when an actor attempts a forbidden action on their own account."""
