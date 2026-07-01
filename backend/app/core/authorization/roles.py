from typing import Literal

SUPER_ADMIN_ROLE = "SuperAdmin"

UserRole = Literal["SuperAdmin", "Admin", "Engineer", "Operator", "Viewer"]

USER_ROLES: frozenset[str] = frozenset(
    {"SuperAdmin", "Admin", "Engineer", "Operator", "Viewer"},
)

ROLE_HIERARCHY: tuple[str, ...] = (
    SUPER_ADMIN_ROLE,
    "Admin",
    "Engineer",
    "Operator",
    "Viewer",
)
