"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  clearToken,
  forgotPassword,
  resetPassword,
} from "../lib/api";

const RESEND_SECONDS = 60;

export default function ResetPasswordForm() {
  const params = useSearchParams();
  const email = params.get("email") ?? "";

  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [cooldown, setCooldown] = useState(
    params.get("sent") === "1" ? RESEND_SECONDS : 0,
  );

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setSubmitting(true);
    try {
      await resetPassword(email, code, password);
      clearToken();
      setDone(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the server. Is the API running?",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    setError(null);
    setInfo(null);
    try {
      await forgotPassword(email);
      setInfo("If an account exists for this email, a new code has been sent.");
      setCooldown(RESEND_SECONDS);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the server. Is the API running?",
      );
    }
  }

  if (!email) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
        <h1 className="text-3xl font-semibold">DRL2</h1>
        <p className="text-sm opacity-70">
          We could not tell which account to reset.
        </p>
        <Link href="/forgot-password" className="text-sm underline">
          Start over
        </Link>
      </main>
    );
  }

  if (done) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
        <h1 className="text-3xl font-semibold">Password updated</h1>
        <p className="text-sm opacity-70">
          You can now sign in with your new password.
        </p>
        <Link
          href="/login"
          className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background"
        >
          Sign in
        </Link>
      </main>
    );
  }

  const inputClass =
    "rounded-lg border border-current/20 bg-transparent px-3 py-2 outline-none focus:border-current/60";

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-3xl font-semibold">Choose a new password</h1>
        <p className="mt-2 text-sm opacity-70">
          Enter the 6-digit code sent to
          <br />
          <span className="font-medium opacity-100">{email}</span>
        </p>
      </div>
      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-sm flex-col gap-4"
      >
        <input
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          placeholder="000000"
          aria-label="Reset code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          className="rounded-lg border border-current/20 bg-transparent px-3 py-3 text-center text-2xl tracking-[0.5em] outline-none focus:border-current/60"
        />
        <label className="flex flex-col gap-1 text-sm">
          New password
          <input
            type="password"
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </label>
        {error && (
          <p role="alert" className="text-center text-sm text-red-500">
            {error}
          </p>
        )}
        {info && <p className="text-center text-sm opacity-70">{info}</p>}
        <button
          type="submit"
          disabled={submitting || code.length !== 6}
          className="rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background disabled:opacity-50"
        >
          {submitting ? "Updating..." : "Reset password"}
        </button>
      </form>
      <div className="flex flex-col items-center gap-2 text-sm">
        <button
          type="button"
          onClick={handleResend}
          disabled={cooldown > 0}
          className="underline disabled:no-underline disabled:opacity-50"
        >
          {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
        </button>
        <Link href="/forgot-password" className="underline opacity-70">
          Use a different email
        </Link>
      </div>
    </main>
  );
}
