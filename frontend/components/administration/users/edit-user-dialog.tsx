"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  UserRoleBadge,
  UserStatusBadge,
} from "@/components/administration/user-badges";
import { AdminDialog } from "@/components/administration/users/admin-dialog";
import { FormField, FormMessage } from "@/components/common/form-field";
import { Input } from "@/components/ui/input";
import { formatDateTime } from "@/lib/dashboard/format";
import {
  canAssignRole,
  canManageUser,
  getCreatableRoles,
} from "@/lib/administration/user-management-policy";
import type { AdminUser } from "@/types/administration";

const roleSchema = z.object({
  role: z.string().min(1, "Role is required"),
});

const passwordSchema = z
  .object({
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Confirm the new password"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RoleFormValues = z.infer<typeof roleSchema>;
type PasswordFormValues = z.infer<typeof passwordSchema>;

type EditUserDialogProps = {
  user: AdminUser | null;
  open: boolean;
  onClose: () => void;
  actorRole: string;
  actorUserId: string;
  onChangeRole: (userId: string, role: string) => Promise<void>;
  onSetActiveStatus: (userId: string, isActive: boolean) => Promise<void>;
  onResetPassword: (userId: string, newPassword: string) => Promise<void>;
};

export function EditUserDialog({
  user,
  open,
  onClose,
  actorRole,
  actorUserId,
  onChangeRole,
  onSetActiveStatus,
  onResetPassword,
}: EditUserDialogProps) {
  const [actionError, setActionError] = useState<string | null>(null);
  const [isUpdatingRole, setIsUpdatingRole] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isResettingPassword, setIsResettingPassword] = useState(false);

  const manageable = user ? canManageUser(actorRole, user.role) : false;
  const isSelf = user?.id === actorUserId;
  const assignableRoles = getCreatableRoles(actorRole).filter((role) =>
    canAssignRole(actorRole, role),
  );

  const roleForm = useForm<RoleFormValues>({
    resolver: zodResolver(roleSchema),
    defaultValues: { role: user?.role ?? "Viewer" },
  });

  const passwordForm = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  useEffect(() => {
    if (user) {
      roleForm.reset({ role: user.role });
      passwordForm.reset({ new_password: "", confirm_password: "" });
      setActionError(null);
    }
  }, [user, roleForm, passwordForm]);

  if (!user) {
    return null;
  }

  const handleClose = () => {
    setActionError(null);
    onClose();
  };

  const submitRole = roleForm.handleSubmit(async (values) => {
    if (!manageable || isSelf) {
      return;
    }

    setActionError(null);
    setIsUpdatingRole(true);

    try {
      await onChangeRole(user.id, values.role);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to update role.");
    } finally {
      setIsUpdatingRole(false);
    }
  });

  const submitPassword = passwordForm.handleSubmit(async (values) => {
    if (!manageable) {
      return;
    }

    setActionError(null);
    setIsResettingPassword(true);

    try {
      await onResetPassword(user.id, values.new_password);
      passwordForm.reset({ new_password: "", confirm_password: "" });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to reset password.");
    } finally {
      setIsResettingPassword(false);
    }
  });

  const toggleStatus = async () => {
    if (!manageable || isSelf) {
      return;
    }

    setActionError(null);
    setIsUpdatingStatus(true);

    try {
      await onSetActiveStatus(user.id, !user.isActive);
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Failed to update account status.",
      );
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  return (
    <AdminDialog
      open={open}
      onClose={handleClose}
      title="Edit user"
      description="Update role assignment, account status, or credentials."
    >
      <div className="space-y-6">
        <div className="rounded-xl border border-border bg-[var(--surface-secondary)]/50 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-base font-medium text-white">{user.fullName}</p>
            <UserRoleBadge role={user.role} />
            <UserStatusBadge isActive={user.isActive} />
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{user.email}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Joined {formatDateTime(user.createdAt)}
          </p>
        </div>

        {!manageable ? (
          <div className="rounded-xl border border-border bg-[var(--surface-secondary)]/30 p-4 text-sm text-muted-foreground">
            Your role cannot modify this account.
          </div>
        ) : null}

        <section className="space-y-3">
          <h4 className="text-sm font-medium text-white">Role assignment</h4>
          <form className="space-y-3" onSubmit={submitRole}>
            <FormField
              label="Role"
              htmlFor="edit-role"
              error={roleForm.formState.errors.role?.message}
            >
              <select
                id="edit-role"
                disabled={!manageable || isSelf || isUpdatingRole}
                {...roleForm.register("role")}
                className="h-12 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-4 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              >
                {assignableRoles.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </FormField>
            {isSelf ? (
              <p className="text-xs text-muted-foreground">
                You cannot change your own role.
              </p>
            ) : null}
            <button
              type="submit"
              disabled={!manageable || isSelf || isUpdatingRole}
              className="h-10 rounded-xl border border-border px-4 text-sm font-medium text-foreground transition-industrial hover:bg-[var(--surface-secondary)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isUpdatingRole ? "Saving role…" : "Save role"}
            </button>
          </form>
        </section>

        <section className="space-y-3">
          <h4 className="text-sm font-medium text-white">Account status</h4>
          <div className="flex items-center justify-between rounded-xl border border-border bg-[var(--surface-secondary)]/30 p-4">
            <div>
              <p className="text-sm text-white">
                {user.isActive ? "Account is active" : "Account is inactive"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {user.isActive
                  ? "User can sign in and access assigned modules."
                  : "User sign-in is blocked until reactivated."}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void toggleStatus()}
              disabled={!manageable || isSelf || isUpdatingStatus}
              className={`h-10 rounded-xl px-4 text-sm font-medium transition-industrial disabled:cursor-not-allowed disabled:opacity-50 ${
                user.isActive
                  ? "border border-[var(--danger)]/30 text-[var(--danger)] hover:bg-[var(--danger)]/10"
                  : "bg-[var(--accent-steel)] text-white hover:bg-[#6a8eb5]"
              }`}
            >
              {isUpdatingStatus
                ? "Updating…"
                : user.isActive
                  ? "Deactivate"
                  : "Activate"}
            </button>
          </div>
          {isSelf ? (
            <p className="text-xs text-muted-foreground">
              You cannot deactivate your own account.
            </p>
          ) : null}
        </section>

        <section className="space-y-3">
          <h4 className="text-sm font-medium text-white">Reset password</h4>
          <form className="space-y-3" onSubmit={submitPassword}>
            <FormField
              label="New password"
              htmlFor="edit-new-password"
              error={passwordForm.formState.errors.new_password?.message}
            >
              <Input
                id="edit-new-password"
                type="password"
                disabled={!manageable || isResettingPassword}
                {...passwordForm.register("new_password")}
              />
            </FormField>
            <FormField
              label="Confirm password"
              htmlFor="edit-confirm-password"
              error={passwordForm.formState.errors.confirm_password?.message}
            >
              <Input
                id="edit-confirm-password"
                type="password"
                disabled={!manageable || isResettingPassword}
                {...passwordForm.register("confirm_password")}
              />
            </FormField>
            <button
              type="submit"
              disabled={!manageable || isResettingPassword}
              className="h-10 rounded-xl border border-border px-4 text-sm font-medium text-foreground transition-industrial hover:bg-[var(--surface-secondary)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isResettingPassword ? "Resetting…" : "Reset password"}
            </button>
          </form>
        </section>

        {actionError ? <FormMessage variant="error">{actionError}</FormMessage> : null}
      </div>
    </AdminDialog>
  );
}
