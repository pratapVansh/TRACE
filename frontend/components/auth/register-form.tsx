"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { InlineLoading } from "@/components/auth/auth-loading-screen";
import { FormField, FormMessage } from "@/components/common/form-field";
import { AuthLink, AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { AUTH_ROUTES } from "@/lib/auth/routes";

const registerSchema = z
  .object({
    full_name: z.string().trim().min(1, "Full name is required"),
    email: z.string().email("Enter a valid email address"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string().min(1, "Confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export function RegisterForm() {
  const router = useRouter();
  const { register: registerUser } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await registerUser({
        full_name: values.full_name,
        email: values.email,
        password: values.password,
      });

      setSuccessMessage("Registration successful. You can now sign in.");
      setTimeout(() => {
        router.push(AUTH_ROUTES.login);
      }, 900);
    } catch (error) {
      if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        setErrorMessage(
          typeof detail === "string"
            ? detail
            : "Unable to complete registration. Please review your details.",
        );
        return;
      }

      setErrorMessage("Unable to complete registration. Please try again.");
    }
  });

  return (
    <AuthShell
      title="Create your TRACE account"
      subtitle="Register for secure access to technical records, asset intelligence, and compliance workflows."
      footer={
        <>
          Already have an account?{" "}
          <AuthLink href={AUTH_ROUTES.login}>Sign in</AuthLink>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5">
        {errorMessage ? (
          <FormMessage variant="error">{errorMessage}</FormMessage>
        ) : null}

        {successMessage ? (
          <FormMessage variant="success">{successMessage}</FormMessage>
        ) : null}

        <FormField
          label="Full name"
          htmlFor="full_name"
          error={errors.full_name?.message}
        >
          <Input
            id="full_name"
            autoComplete="name"
            placeholder="Jane Engineer"
            aria-invalid={Boolean(errors.full_name)}
            {...register("full_name")}
          />
        </FormField>

        <FormField label="Email" htmlFor="email" error={errors.email?.message}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="engineer@company.com"
            aria-invalid={Boolean(errors.email)}
            {...register("email")}
          />
        </FormField>

        <FormField
          label="Password"
          htmlFor="password"
          error={errors.password?.message}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            placeholder="Minimum 8 characters"
            aria-invalid={Boolean(errors.password)}
            {...register("password")}
          />
        </FormField>

        <FormField
          label="Confirm password"
          htmlFor="confirmPassword"
          error={errors.confirmPassword?.message}
        >
          <Input
            id="confirmPassword"
            type="password"
            autoComplete="new-password"
            placeholder="Re-enter your password"
            aria-invalid={Boolean(errors.confirmPassword)}
            {...register("confirmPassword")}
          />
        </FormField>

        <Button
          type="submit"
          disabled={isSubmitting}
          className="mt-2 h-12 w-full rounded-xl bg-[var(--accent-steel)] text-base font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <InlineLoading />
              Creating account
            </span>
          ) : (
            "Create account"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
