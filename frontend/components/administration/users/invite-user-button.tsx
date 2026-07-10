"use client";

import { UserPlus, X } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { USER_ROLES } from "@/lib/administration/constants";

type InviteUserDialogProps = {
  open: boolean;
  onClose: () => void;
};

export function InviteUserDialog({ open, onClose }: InviteUserDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog backdrop"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md industrial-card p-6 sm:p-8">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="section-label">Administration</p>
            <h3 className="mt-1 text-xl font-semibold text-white">Invite user</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Send an invitation to join the workspace.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-muted-foreground hover:bg-[var(--surface-secondary)] hover:text-white"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
          <div className="space-y-2">
            <Label htmlFor="invite-email">Email address</Label>
            <Input id="invite-email" type="email" placeholder="engineer@company.com" disabled />
          </div>
          <div className="space-y-2">
            <Label htmlFor="invite-name">Full name</Label>
            <Input id="invite-name" placeholder="Jane Engineer" disabled />
          </div>
          <div className="space-y-2">
            <Label htmlFor="invite-role">Role</Label>
            <select
              id="invite-role"
              disabled
              className="h-12 w-full rounded-xl border border-border bg-[var(--surface-secondary)] px-4 text-sm text-muted-foreground"
            >
              {USER_ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </div>
          <p className="text-xs text-muted-foreground">
            Invitations require backend integration — preview UI only.
          </p>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="h-11 flex-1 rounded-xl border border-border text-sm font-medium text-foreground hover:bg-[var(--surface-secondary)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled
              className="h-11 flex-1 rounded-xl bg-[var(--accent-steel)]/50 text-sm font-medium text-white/60"
            >
              Send invitation
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function InviteUserButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-10 items-center gap-2 rounded-xl bg-[var(--accent-steel)] px-4 text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
      >
        <UserPlus className="size-4" />
        Invite user
      </button>
      <InviteUserDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}
