from enum import StrEnum

from app.core.authorization.roles import SUPER_ADMIN_ROLE, USER_ROLES, UserRole


class Permission(StrEnum):
    """Canonical permission identifiers for backend authorization."""
    DASHBOARD = "dashboard"
    DOCUMENTS_READ = "documents_read"
    DOCUMENTS_UPLOAD = "documents_upload"
    SEARCH = "search"
    COPILOT = "copilot"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    ASSETS_READ = "assets_read"
    ASSETS_WRITE = "assets_write"
    MAINTENANCE = "maintenance"
    COMPLIANCE = "compliance"
    SOP_LIBRARY = "sop_library"
    USER_MANAGEMENT = "user_management"
    ROLE_MANAGEMENT = "role_management"
    SYSTEM_SETTINGS = "system_settings"


ALL_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    "Admin": ALL_PERMISSIONS,
    "Engineer": frozenset(
        {
            Permission.DASHBOARD,
            Permission.DOCUMENTS_READ,
            Permission.DOCUMENTS_UPLOAD,
            Permission.SEARCH,
            Permission.COPILOT,
            Permission.KNOWLEDGE_GRAPH,
            Permission.ASSETS_READ,
            Permission.ASSETS_WRITE,
            Permission.MAINTENANCE,
            Permission.COMPLIANCE,
            Permission.SOP_LIBRARY,
        }
    ),
    "Operator": frozenset(
        {
            Permission.DASHBOARD,
            Permission.DOCUMENTS_READ,
            Permission.SEARCH,
            Permission.COPILOT,
            Permission.MAINTENANCE,
        }
    ),
    "Viewer": frozenset(
        {
            Permission.DASHBOARD,
            Permission.DOCUMENTS_READ,
            Permission.SEARCH,
        }
    ),
}


def is_user_role(value: str) -> bool:
    return value in USER_ROLES


def get_permissions_for_role(role: str) -> frozenset[Permission]:
    if role == SUPER_ADMIN_ROLE:
        return ALL_PERMISSIONS
    if not is_user_role(role):
        return frozenset()
    return ROLE_PERMISSIONS[role]


def has_permission(role: str, permission: Permission) -> bool:
    return permission in get_permissions_for_role(role)


PERMISSIONS = Permission
