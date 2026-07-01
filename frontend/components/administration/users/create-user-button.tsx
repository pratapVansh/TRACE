"use client";

import { UserPlus } from "lucide-react";
import { useState } from "react";

import { CreateUserDialog } from "@/components/administration/users/create-user-dialog";

type CreateUserButtonProps = {
  actorRole: string;
  onCreateUser: (values: {
    full_name: string;
    email: string;
    password: string;
    role: string;
  }) => Promise<void>;
};

export function CreateUserButton({ actorRole, onCreateUser }: CreateUserButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-10 items-center gap-2 rounded-xl bg-[var(--accent-steel)] px-4 text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
      >
        <UserPlus className="size-4" />
        Create user
      </button>
      <CreateUserDialog
        open={open}
        onClose={() => setOpen(false)}
        actorRole={actorRole}
        onSubmit={async (values) => {
          await onCreateUser(values);
        }}
      />
    </>
  );
}
