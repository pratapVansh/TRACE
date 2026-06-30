import { GuestGuard } from "@/components/auth/auth-guard";
import { RegisterForm } from "@/components/auth/register-form";

export default function RegisterPage() {
  return (
    <GuestGuard>
      <RegisterForm />
    </GuestGuard>
  );
}
