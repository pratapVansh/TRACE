"use client";

import { isAxiosError } from "axios";
import { useCallback, useEffect, useState } from "react";

import {
  createAdminUser,
  listAdminUsers,
  resetAdminUserPassword,
  updateAdminUserRole,
  updateAdminUserStatus,
} from "@/lib/api/admin-users";
import { mapAdminUserFromApi } from "@/lib/administration/utils";
import type {
  AdminUser,
  CreateAdminUserPayload,
} from "@/types/administration";

function getErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export function useAdminUsers() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await listAdminUsers({ skip: 0, limit: 500 });
      setUsers(response.items.map(mapAdminUserFromApi));
      setTotal(response.total);
    } catch (fetchError) {
      setError(getErrorMessage(fetchError, "Failed to load users."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchUsers();
  }, [fetchUsers]);

  const createUser = useCallback(
    async (payload: CreateAdminUserPayload) => {
      try {
        const created = await createAdminUser(payload);
        await fetchUsers();
        return mapAdminUserFromApi(created);
      } catch (createError) {
        throw new Error(getErrorMessage(createError, "Failed to create user."));
      }
    },
    [fetchUsers],
  );

  const changeRole = useCallback(
    async (userId: string, role: string) => {
      try {
        await updateAdminUserRole(userId, { role });
        await fetchUsers();
      } catch (updateError) {
        throw new Error(getErrorMessage(updateError, "Failed to update role."));
      }
    },
    [fetchUsers],
  );

  const setActiveStatus = useCallback(
    async (userId: string, isActive: boolean) => {
      try {
        await updateAdminUserStatus(userId, { is_active: isActive });
        await fetchUsers();
      } catch (updateError) {
        throw new Error(
          getErrorMessage(updateError, "Failed to update account status."),
        );
      }
    },
    [fetchUsers],
  );

  const resetPassword = useCallback(
    async (userId: string, newPassword: string) => {
      try {
        await resetAdminUserPassword(userId, { new_password: newPassword });
        await fetchUsers();
      } catch (updateError) {
        throw new Error(getErrorMessage(updateError, "Failed to reset password."));
      }
    },
    [fetchUsers],
  );

  return {
    users,
    total,
    isLoading,
    error,
    refresh: fetchUsers,
    createUser,
    changeRole,
    setActiveStatus,
    resetPassword,
  };
}
