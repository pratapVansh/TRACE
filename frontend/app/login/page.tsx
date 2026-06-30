import { GuestGuard } from "@/components/auth/auth-guard";
import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <GuestGuard>
      <LoginForm />
    </GuestGuard>
  );
}
