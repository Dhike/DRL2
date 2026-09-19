"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import Avatar from "../../components/Avatar";
import { useUser } from "../../components/UserContext";
import { ApiError, clearToken, forgotPassword } from "../../lib/api";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-current/15 p-4">
      <h2 className="text-xs font-medium uppercase tracking-wide opacity-60">
        {title}
      </h2>
      <div className="mt-3 flex flex-col gap-3 text-sm">{children}</div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="opacity-60">{label}</span>
      <span className="truncate text-right">{value}</span>
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "Not verified";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function AccountPage() {
  const user = useUser();
  const router = useRouter();
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleResetPassword() {
    setError(null);
    setSending(true);
    try {
      await forgotPassword(user.email);
      router.push(
        `/reset-password?email=${encodeURIComponent(user.email)}&sent=1`,
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the server. Is the API running?",
      );
      setSending(false);
    }
  }

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  const buttonClass =
    "rounded-lg border border-current/20 px-3 py-2 text-sm hover:bg-current/5 disabled:opacity-50";

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex flex-col items-center gap-2 py-4 text-center">
        <Avatar size={80} />
        <h1 className="mt-2 text-lg font-semibold">{user.email}</h1>
        <span className="rounded-full border border-current/20 px-3 py-0.5 text-xs capitalize opacity-70">
          {user.role}
        </span>
      </div>

      <Section title="Profile">
        <Row label="Email" value={user.email} />
        <Row label="Role" value={user.role} />
        <Row label="Email verified" value={formatDate(user.email_verified_at)} />
        <Row label="Member since" value={formatDate(user.created_at)} />
      </Section>

      <Section title="Security">
        <div>
          <p className="opacity-70">
            Reset your password. We will email a 6-digit code to {user.email}.
          </p>
          <button
            type="button"
            onClick={handleResetPassword}
            disabled={sending}
            className={`mt-3 ${buttonClass}`}
          >
            {sending ? "Sending code..." : "Send reset code"}
          </button>
          {error && (
            <p role="alert" className="mt-2 text-sm text-red-500">
              {error}
            </p>
          )}
        </div>
      </Section>

      <Section title="Session">
        <button
          type="button"
          onClick={handleLogout}
          className={`flex items-center justify-center gap-2 ${buttonClass}`}
        >
          <LogOut size={16} />
          Log out
        </button>
      </Section>
    </div>
  );
}
