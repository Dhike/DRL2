"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import Avatar from "../../components/Avatar";
import { useUser } from "../../components/UserContext";
import {
  ApiError,
  changePassword,
  clearToken,
  forgotPassword,
} from "../../lib/api";

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

const inputClass =
  "rounded-lg border border-current/20 bg-transparent px-3 py-2 outline-none focus:border-current/60";
const buttonClass =
  "rounded-lg border border-current/20 px-3 py-2 text-sm hover:bg-current/5 disabled:opacity-50";

export default function AccountPage() {
  const user = useUser();
  const router = useRouter();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [changing, setChanging] = useState(false);
  const [changeError, setChangeError] = useState<string | null>(null);
  const [changeDone, setChangeDone] = useState(false);

  const [sending, setSending] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setChangeError(null);
    setChangeDone(false);
    if (next !== confirm) {
      setChangeError("The new passwords do not match.");
      return;
    }
    setChanging(true);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setChangeDone(true);
    } catch (err) {
      setChangeError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the server. Is the API running?",
      );
    } finally {
      setChanging(false);
    }
  }

  async function handleResetPassword() {
    setResetError(null);
    setSending(true);
    try {
      await forgotPassword(user.email);
      router.push(
        `/reset-password?email=${encodeURIComponent(user.email)}&sent=1`,
      );
    } catch (err) {
      setResetError(
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

      <Section title="Change password">
        <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            Current password
            <input
              type="password"
              required
              maxLength={128}
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1">
            New password (at least 8 characters)
            <input
              type="password"
              required
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1">
            Confirm new password
            <input
              type="password"
              required
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={inputClass}
            />
          </label>
          {changeError && (
            <p role="alert" className="text-red-500">
              {changeError}
            </p>
          )}
          {changeDone && (
            <p role="status" className="text-green-500">
              Password updated. Any other devices have been signed out.
            </p>
          )}
          <button type="submit" disabled={changing} className={buttonClass}>
            {changing ? "Updating..." : "Change password"}
          </button>
        </form>
      </Section>

      <Section title="Forgot your password?">
        <p className="opacity-70">
          Reset it with a 6-digit code emailed to {user.email}.
        </p>
        <button
          type="button"
          onClick={handleResetPassword}
          disabled={sending}
          className={buttonClass}
        >
          {sending ? "Sending code..." : "Send reset code"}
        </button>
        {resetError && (
          <p role="alert" className="text-red-500">
            {resetError}
          </p>
        )}
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
