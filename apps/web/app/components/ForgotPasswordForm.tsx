"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ApiError, forgotPassword } from "../lib/api";
import AuthShell from "./ui/AuthShell";
import Button from "./ui/Button";
import { Field, Input } from "./ui/Input";
import Message from "./ui/Message";

export default function ForgotPasswordForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await forgotPassword(email);
      router.push(
        `/reset-password?email=${encodeURIComponent(email.trim())}&sent=1`,
      );
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

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your email and we will send you a 6-digit code."
      footer={
        <Link href="/login" className="hover:underline">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Field label="Email">
          <Input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        {error && <Message kind="error">{error}</Message>}
        <Button type="submit" disabled={submitting}>
          {submitting ? "Please wait..." : "Send code"}
        </Button>
      </form>
    </AuthShell>
  );
}
