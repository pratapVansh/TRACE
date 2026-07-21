"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { InlineLoading } from "@/components/auth/auth-loading-screen";
import { FormField, FormMessage } from "@/components/common/form-field";
import { AuthLink } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { TraceLogo } from "@/components/common/trace-logo";
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
    <div className="flex min-h-screen">
      {/* Left — Brand / Image Panel */}
      <div className="relative hidden w-1/2 lg:block">
        <div
          className="absolute inset-0 bg-cover bg-center brightness-[0.85]"
          style={{
            backgroundImage:
              'url("https://images.unsplash.com/photo-1577097997335-658d0356a7f3?q=80&w=1080&auto=format&fit=crop")',
          }}
        />
        <div className="absolute inset-0 bg-black/20" />

        <div className="absolute inset-0 flex flex-col p-12 xl:p-16">
          <div className="[&>div>div]:!bg-[var(--accent-steel)] [&>div>div]:!border-[var(--accent-steel)] [&>div>div]:!text-white [&>div>span]:!text-white">
            <TraceLogo size="md" />
          </div>

          <div className="flex flex-1 flex-col justify-center">
            <div className="max-w-lg">
            <p className="text-[13px] font-medium tracking-[0.15em] text-white/70 uppercase" style={{ textShadow: "0 1px 4px rgba(0,0,0,0.5)" }}>
              TRACE Platform
            </p>
            <h1 className="mt-3 text-4xl leading-[1.15] font-semibold text-white xl:text-5xl" style={{ textShadow: "0 2px 8px rgba(0,0,0,0.6)" }}>
              Engineer&apos;s Best Friend
            </h1>
            <p className="mt-4 max-w-md text-base leading-relaxed text-white/80" style={{ textShadow: "0 1px 4px rgba(0,0,0,0.5)" }}>
              Technical Records & Asset Compliance Engine — built for
              engineers, plant managers, and reliability teams.
            </p>
          </div>

        </div>
        </div>
      </div>

      {/* Right — Login Form */}
      <div className="flex w-full items-center justify-center px-6 sm:px-10 lg:w-1/2">
        <div className="w-full max-w-[400px] animate-in fade-in slide-in-from-bottom-1 duration-200">
          {/* Mobile logo */}
          <div className="mb-10 lg:hidden">
          <div className="[&>div>div]:!bg-[var(--accent-steel)] [&>div>div]:!border-[var(--accent-steel)] [&>div>div]:!text-white [&>div>span]:!text-white">
            <TraceLogo size="md" />
          </div>
          </div>

          <div className="space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-[1.65rem]">
              Welcome back
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Sign in to your account to continue.
            </p>
          </div>

          <form onSubmit={onSubmit} className="mt-8 space-y-5">
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

            <div className="flex items-center justify-between">
              <label className="flex cursor-pointer items-center gap-2.5 text-sm text-[var(--text-secondary)]">
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
                className="text-sm text-[var(--accent-steel-muted)] transition-industrial hover:text-[var(--accent-steel)]"
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

          <p className="mt-8 text-center text-sm text-[var(--text-secondary)]">
            New to TRACE?{" "}
            <AuthLink href={AUTH_ROUTES.register}>Create an account</AuthLink>
          </p>
        </div>
      </div>
    </div>
  );
}
