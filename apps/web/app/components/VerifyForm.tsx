"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError, resendCode, verifyEmail } from "../lib/api";

const RESEND_SECONDS = 60;

export default function VerifyForm() {
  const router = useRouter();
  const params = useSearchParams();
  const email = params.get("email") ?? "";

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
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
      await verifyEmail(email, code);
      router.push("/");
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
      await resendCode(email);
      setInfo("A new code has been requested. Check your email.");
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
          We could not tell which email to verify.
        </p>
        <Link href="/login" className="text-sm underline">
          Go to sign in
        </Link>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-3xl font-semibold">Verify your email</h1>
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
          aria-label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          className="rounded-lg border border-current/20 bg-transparent px-3 py-3 text-center text-2xl tracking-[0.5em] outline-none focus:border-current/60"
        />
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
          {submitting ? "Checking..." : "Verify email"}
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
        <Link href="/register" className="opacity-70 underline">
          Wrong email? Start over
        </Link>
      </div>
    </main>
  );
}
