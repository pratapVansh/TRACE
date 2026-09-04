"use client";

import { Pencil } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CreateUserButton } from "@/components/administration/users/create-user-button";
import { EditUserDialog } from "@/components/administration/users/edit-user-dialog";
import {
  UserRoleBadge,
  UserStatusBadge,
} from "@/components/administration/user-badges";
import { UserFilters } from "@/components/administration/users/user-filters";
import { UsersPagination } from "@/components/administration/users/users-pagination";
import { PageHeader } from "@/components/common/page-header";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { DataTable } from "@/components/operations/data-table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminUsers } from "@/hooks/use-admin-users";
import { useAuth } from "@/hooks/use-auth";
import { USER_ROLES } from "@/lib/administration/constants";
import { filterVisibleUsers } from "@/lib/administration/user-management-policy";
import {
  filterAdminUsers,
  paginateUsers,
} from "@/lib/administration/utils";
import { formatDateTime } from "@/lib/dashboard/format";
import type { AdminUser } from "@/types/administration";
import { SUPER_ADMIN_ROLE } from "@/types/permissions";

const PAGE_SIZE = 10;

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
];

export function UsersPageContent() {
  const { user } = useAuth();
  const {
    users,
    total,
    isLoading,
    error,
    refresh,
    createUser,
    changeRole,
    setActiveStatus,
    resetPassword,
  } = useAdminUsers();

  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  const actorRole = user?.role ?? "";

  const visibleUsers = useMemo(
    () => filterVisibleUsers(users, actorRole),
    [users, actorRole],
  );

  const filteredUsers = useMemo(
    () =>
      filterAdminUsers(visibleUsers, query, {
        role: roleFilter,
        status: statusFilter,
      }),
    [visibleUsers, query, roleFilter, statusFilter],
  );

  useEffect(() => {
    setPage(1);
  }, [query, roleFilter, statusFilter]);

  const paginatedUsers = useMemo(
    () => paginateUsers(filteredUsers, page, PAGE_SIZE),
    [filteredUsers, page],
  );

  const roleOptions = useMemo(() => {
    const roles =
      actorRole === SUPER_ADMIN_ROLE
        ? USER_ROLES
        : USER_ROLES.filter((role) => role !== SUPER_ADMIN_ROLE);

    return [
      { value: "all", label: "All roles" },
      ...roles.map((role) => ({ value: role, label: role })),
    ];
  }, [actorRole]);

  const columns = [
    {
      key: "user",
      header: "User",
      render: (row: AdminUser) => (
        <div className="space-y-1">
          <p className="font-medium text-foreground">{row.fullName}</p>
          <p className="text-xs text-muted-foreground">{row.email}</p>
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      render: (row: AdminUser) => <UserRoleBadge role={row.role} />,
    },
    {
      key: "status",
      header: "Status",
      render: (row: AdminUser) => <UserStatusBadge isActive={row.isActive} />,
    },
    {
      key: "joined",
      header: "Joined",
      render: (row: AdminUser) => (
        <span className="text-muted-foreground">{formatDateTime(row.createdAt)}</span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      render: (row: AdminUser) => (
        <Button
          variant="ghost"
          size="sm"
          className="rounded-lg text-muted-foreground hover:text-foreground"
          onClick={() => setSelectedUser(row)}
          aria-label={`Edit ${row.fullName}`}
        >
          <Pencil className="size-4" />
          Edit
        </Button>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
        <PageHeader
          sectionLabel="Administration"
          title="Users"
          description="Manage platform users, role assignments, and account status."
        />
        <div className="space-y-4">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
        <PageHeader
          sectionLabel="Administration"
          title="Users"
          description="Manage platform users, role assignments, and account status."
        />
        <div className="industrial-card flex flex-col items-center gap-4 p-10 text-center">
          <p className="text-sm text-[var(--danger)]">{error}</p>
          <button
            type="button"
            onClick={() => void refresh()}
            className="h-10 rounded-xl border border-border px-4 text-sm text-foreground hover:bg-[var(--surface-secondary)]"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Administration"
        title="Users"
        description="Manage platform users, role assignments, and account status."
        action={
          <CreateUserButton
            actorRole={actorRole}
            onCreateUser={async (values) => {
              await createUser(values);
            }}
          />
        }
      />

      <KnowledgeSearchBar
        value={query}
        onChange={setQuery}
        placeholder="Search by name, email, or role…"
      />

      <UserFilters
        role={roleFilter}
        status={statusFilter}
        roleOptions={roleOptions}
        statusOptions={STATUS_OPTIONS}
        onRoleChange={setRoleFilter}
        onStatusChange={setStatusFilter}
        onClear={() => {
          setRoleFilter("all");
          setStatusFilter("all");
        }}
      />

      <DataTable
        columns={columns}
        data={paginatedUsers}
        rowKey={(row) => row.id}
        minWidth="900px"
        emptyMessage="No users match the current search or filters."
        footer={
          <UsersPagination
            page={page}
            pageSize={PAGE_SIZE}
            totalItems={filteredUsers.length}
            onPageChange={setPage}
          />
        }
      />

      <p className="text-xs text-muted-foreground">
        {total} total accounts in the organization
        {actorRole !== SUPER_ADMIN_ROLE ? " (SuperAdmin accounts hidden)" : ""}
      </p>

      <EditUserDialog
        user={selectedUser}
        open={selectedUser !== null}
        onClose={() => setSelectedUser(null)}
        actorRole={actorRole}
        actorUserId={user?.id ?? ""}
        onChangeRole={changeRole}
        onSetActiveStatus={setActiveStatus}
        onResetPassword={resetPassword}
      />
    </div>
  );
}
