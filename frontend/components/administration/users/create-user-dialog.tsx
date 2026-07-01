"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AdminDialog } from "@/components/administration/users/admin-dialog";
import { FormField, FormMessage } from "@/components/common/form-field";
import { Input } from "@/components/ui/input";
import { getCreatableRoles } from "@/lib/administration/user-management-policy";

const createUserSchema = z.object({
  full_name: z.string().trim().min(1, "Full name is required"),
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  role: z.string().min(1, "Role is required"),
});

type CreateUserFormValues = z.infer<typeof createUserSchema>;

type CreateUserDialogProps = {
  open: boolean;
  onClose: () => void;
  actorRole: string;
  onSubmit: (values: CreateUserFormValues) => Promise<void>;
};

export function CreateUserDialog({
  open,
  onClose,
  actorRole,
  onSubmit,
}: CreateUserDialogProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const roleOptions = getCreatableRoles(actorRole);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      role: roleOptions[0] ?? "Viewer",
    },
  });

  const handleClose = () => {
    reset();
    setErrorMessage(null);
    onClose();
  };

  const submit = handleSubmit(async (values) => {
    setErrorMessage(null);

    try {
      await onSubmit({
        ...values,
        email: values.email.toLowerCase().trim(),
        full_name: values.full_name.trim(),
      });
      reset();
      onClose();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create user.");
    }
  });

  return (
    <AdminDialog
      open={open}
      onClose={handleClose}
      title="Create user"
      description="Provision a new platform account with an assigned role."
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            disabled={isSubmitting}
            className="h-11 flex-1 rounded-xl border border-border text-sm font-medium text-foreground hover:bg-[var(--surface-secondary)] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-user-form"
            disabled={isSubmitting}
            className="h-11 flex-1 rounded-xl bg-[var(--accent-steel)] text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5] disabled:opacity-50"
          >
            {isSubmitting ? "Creating…" : "Create user"}
          </button>
        </>
      }
    >
      <form id="create-user-form" className="space-y-4" onSubmit={submit}>
        <FormField label="Full name" htmlFor="create-full-name" error={errors.full_name?.message}>
          <Input id="create-full-name" placeholder="Jane Engineer" {...register("full_name")} />
        </FormField>

        <FormField label="Email address" htmlFor="create-email" error={errors.email?.message}>
          <Input
            id="create-email"
            type="email"
            placeholder="engineer@company.com"
            {...register("email")}
          />
        </FormField>

        <FormField label="Password" htmlFor="create-password" error={errors.password?.message}>
          <Input
            id="create-password"
            type="password"
            placeholder="Minimum 8 characters"
            {...register("password")}
          />
        </FormField>

        <FormField label="Role" htmlFor="create-role" error={errors.role?.message}>
          <select
            id="create-role"
            {...register("role")}
            className="h-12 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-4 text-sm text-foreground focus-visible:border-[var(--accent-steel)]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-steel)]/15"
          >
            {roleOptions.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </FormField>

        {errorMessage ? <FormMessage variant="error">{errorMessage}</FormMessage> : null}
      </form>
    </AdminDialog>
  );
}
