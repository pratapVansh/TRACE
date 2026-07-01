"""Add SuperAdmin role for enterprise RBAC bootstrap."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_super_admin_role"
down_revision: Union[str, None] = "002_auth_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUPER_ADMIN_ROLE = (
    "SuperAdmin",
    "Organization owner with unrestricted system access",
)


def upgrade() -> None:
    roles_table = sa.table(
        "roles",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        roles_table,
        [{"name": SUPER_ADMIN_ROLE[0], "description": SUPER_ADMIN_ROLE[1]}],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM roles WHERE name = 'SuperAdmin'"))
