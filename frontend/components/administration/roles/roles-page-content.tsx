import { PermissionMatrix } from "@/components/administration/roles/permission-matrix";
import { RoleCard } from "@/components/administration/roles/role-card";
import { PageHeader } from "@/components/common/page-header";
import { ROLE_DEFINITIONS } from "@/lib/administration/mock-data";

export function RolesPageContent() {
  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Administration"
        title="Roles & Permissions"
        description="Define access levels and review the permission matrix for Admin, Engineer, Operator, and Viewer roles."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {ROLE_DEFINITIONS.map((role) => (
          <RoleCard key={role.role} role={role} />
        ))}
      </div>

      <PermissionMatrix />
    </div>
  );
}
