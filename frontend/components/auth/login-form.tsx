"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { InlineLoading } from "@/components/auth/auth-loading-screen";
import { FormField, FormMessage } from "@/components/common/form-field";
import { AuthLink, AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { AUTH_ROUTES } from "@/lib/auth/routes";
import { authStorage } from "@/lib/auth/storage";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
  rememberMe: z.boolean(),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const router = useRouter();
  const { login } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
      rememberMe: false,
    },
  });

  const rememberMe = useWatch({ control, name: "rememberMe" });

  useEffect(() => {
    const rememberedEmail = authStorage.getRememberedEmail();
    if (rememberedEmail) {
      setValue("email", rememberedEmail);
      setValue("rememberMe", true);
    }
  }, [setValue]);

  const onSubmit = handleSubmit(async (values) => {
    setErrorMessage(null);

    try {
      if (values.rememberMe) {
        authStorage.setRememberedEmail(values.email);
      } else {
        authStorage.clearRememberedEmail();
      }

      await login({
        email: values.email,
        password: values.password,
      });

      router.replace(AUTH_ROUTES.dashboard);
    } catch (error) {
      if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        setErrorMessage(
          typeof detail === "string"
            ? detail
            : "Unable to sign in. Check your credentials and try again.",
        );
        return;
      }

      setErrorMessage("Unable to sign in. Please try again.");
    }
  });

  return (
    <AuthShell
      title="Sign in to TRACE"
      subtitle="Access your industrial knowledge workspace with secure enterprise credentials."
      footer={
        <>
          New to TRACE?{" "}
          <AuthLink href={AUTH_ROUTES.register}>Create an account</AuthLink>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-6">
        {errorMessage ? (
          <FormMessage variant="error">{errorMessage}</FormMessage>
        ) : null}

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
            autoComplete="current-password"
            placeholder="Enter your password"
            aria-invalid={Boolean(errors.password)}
            {...register("password")}
          />
        </FormField>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex cursor-pointer items-center gap-2.5 text-sm text-muted-foreground">
            <Checkbox
              checked={rememberMe}
              onChange={(event) =>
                setValue("rememberMe", event.target.checked)
              }
            />
            Remember me
          </label>

          <button
            type="button"
            className="text-left text-sm text-[var(--accent-steel-muted)] transition-industrial hover:text-foreground sm:text-right"
            disabled
            title="Password recovery will be available in a future release"
          >
            Forgot password?
          </button>
        </div>

        <Button
          type="submit"
          disabled={isSubmitting}
          className="h-12 w-full rounded-xl bg-[var(--accent-steel)] text-base font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <InlineLoading />
              Signing in
            </span>
          ) : (
            "Sign in"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
