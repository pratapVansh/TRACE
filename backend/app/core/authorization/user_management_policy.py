from app.core.authorization.roles import SUPER_ADMIN_ROLE

ADMIN_ROLE = "Admin"

ADMIN_MANAGED_ROLES: frozenset[str] = frozenset({"Engineer", "Operator", "Viewer"})

SUPER_ADMIN_CREATABLE_ROLES: frozenset[str] = frozenset(
    {SUPER_ADMIN_ROLE, ADMIN_ROLE, "Engineer", "Operator", "Viewer"},
)

ADMIN_CREATABLE_ROLES: frozenset[str] = ADMIN_MANAGED_ROLES


def creatable_roles_for(actor_role: str) -> frozenset[str]:
    if actor_role == SUPER_ADMIN_ROLE:
        return SUPER_ADMIN_CREATABLE_ROLES
    if actor_role == ADMIN_ROLE:
        return ADMIN_CREATABLE_ROLES
    return frozenset()


def can_manage_user(actor_role: str, target_role: str) -> bool:
    if actor_role == SUPER_ADMIN_ROLE:
        return True
    if actor_role == ADMIN_ROLE:
        return target_role in ADMIN_MANAGED_ROLES
    return False


def can_assign_role(actor_role: str, new_role: str) -> bool:
    return new_role in creatable_roles_for(actor_role)
