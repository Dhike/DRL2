"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Avatar from "../../components/Avatar";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { Field, Input } from "../../components/ui/Input";
import Message from "../../components/ui/Message";
import { useUser } from "../../components/UserContext";
import {
  ApiError,
  changePassword,
  clearToken,
  forgotPassword,
} from "../../lib/api";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-muted">{label}</span>
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
        <Badge tone="accent">{user.role}</Badge>
      </div>

      <Card title="Profile">
        <div className="flex flex-col gap-3">
          <Row label="Email" value={user.email} />
          <Row label="Role" value={user.role} />
          <Row
            label="Email verified"
            value={formatDate(user.email_verified_at)}
          />
          <Row label="Member since" value={formatDate(user.created_at)} />
        </div>
      </Card>

      <Card title="Change password">
        <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
          <Field label="Current password">
            <Input
              type="password"
              required
              maxLength={128}
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </Field>
          <Field label="New password (at least 8 characters)">
            <Input
              type="password"
              required
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          </Field>
          <Field label="Confirm new password">
            <Input
              type="password"
              required
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </Field>
          {changeError && <Message kind="error">{changeError}</Message>}
          {changeDone && (
            <Message kind="success">
              Password updated. Any other devices have been signed out.
            </Message>
          )}
          <Button type="submit" disabled={changing}>
            {changing ? "Updating..." : "Change password"}
          </Button>
        </form>
      </Card>

      <Card title="Forgot your password?">
        <p className="text-sm text-muted">
          Reset it with a 6-digit code emailed to {user.email}.
        </p>
        <Button
          type="button"
          variant="secondary"
          onClick={handleResetPassword}
          disabled={sending}
          className="mt-3 w-full"
        >
          {sending ? "Sending code..." : "Send reset code"}
        </Button>
        {resetError && (
          <Message kind="error" className="mt-2">
            {resetError}
          </Message>
        )}
      </Card>

      <Card title="Session">
        <Button
          type="button"
          variant="danger"
          onClick={handleLogout}
          className="w-full"
        >
          <LogOut size={16} />
          Log out
        </Button>
      </Card>
    </div>
  );
}
