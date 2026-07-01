import type {
  AdminUser,
  AdminUserApiResponse,
} from "@/types/administration";

export function mapAdminUserFromApi(raw: AdminUserApiResponse): AdminUser {
  return {
    id: raw.id,
    email: raw.email,
    fullName: raw.full_name,
    role: raw.role,
    isActive: raw.is_active,
    createdAt: raw.created_at,
  };
}

export function filterAdminUsers(
  users: AdminUser[],
  query: string,
  filters: { role: string; status: string },
): AdminUser[] {
  const q = query.trim().toLowerCase();

  return users.filter((user) => {
    if (filters.role !== "all" && user.role !== filters.role) {
      return false;
    }

    if (filters.status === "active" && !user.isActive) {
      return false;
    }

    if (filters.status === "inactive" && user.isActive) {
      return false;
    }

    if (!q) {
      return true;
    }

    const haystack = [user.fullName, user.email, user.role].join(" ").toLowerCase();
    return haystack.includes(q);
  });
}

export function paginateUsers<T>(items: T[], page: number, pageSize: number): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}
