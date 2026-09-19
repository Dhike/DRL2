"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError, resendCode, verifyEmail } from "../lib/api";
import AuthShell from "./ui/AuthShell";
import Button, { buttonClass } from "./ui/Button";
import { Input } from "./ui/Input";
import Message from "./ui/Message";

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
      <AuthShell
        title="Verify your email"
        subtitle="We could not tell which email to verify."
      >
        <Link href="/login" className={buttonClass("secondary", "w-full")}>
          Go to sign in
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Verify your email"
      subtitle={
        <>
          Enter the 6-digit code sent to
          <br />
          <span className="font-medium text-foreground">{email}</span>
        </>
      }
      footer={
        <Link href="/register" className="hover:underline">
          Wrong email? Start over
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          placeholder="000000"
          aria-label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          className="py-3 text-center text-2xl tracking-[0.5em]"
        />
        {error && (
          <Message kind="error" className="text-center">
            {error}
          </Message>
        )}
        {info && (
          <Message kind="info" className="text-center">
            {info}
          </Message>
        )}
        <Button type="submit" disabled={submitting || code.length !== 6}>
          {submitting ? "Checking..." : "Verify email"}
        </Button>
        <Button
          type="button"
          variant="link"
          onClick={handleResend}
          disabled={cooldown > 0}
        >
          {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
        </Button>
      </form>
    </AuthShell>
  );
}
