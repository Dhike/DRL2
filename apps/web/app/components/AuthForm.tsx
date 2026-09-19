"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ApiError, login, register } from "../lib/api";
import AuthShell from "./ui/AuthShell";
import Button from "./ui/Button";
import { Field, Input } from "./ui/Input";
import Message from "./ui/Message";

type Mode = "login" | "register";

export default function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isLogin = mode === "login";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    const verifyUrl = `/verify?email=${encodeURIComponent(email.trim())}`;
    try {
      if (isLogin) {
        await login(email, password);
        router.push("/");
      } else {
        await register(email, password);
        router.push(`${verifyUrl}&sent=1`);
      }
    } catch (err) {
      if (isLogin && err instanceof ApiError && err.status === 403) {
        router.push(verifyUrl);
        return;
      }
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
      title={isLogin ? "Welcome back" : "Create your account"}
      subtitle={
        isLogin
          ? "Sign in to continue to DRL2"
          : "Start with your email and a password"
      }
      footer={
        <>
          {isLogin ? "No account yet? " : "Already registered? "}
          <Link
            href={isLogin ? "/register" : "/login"}
            className="text-accent hover:underline"
          >
            {isLogin ? "Create one" : "Sign in"}
          </Link>
        </>
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
        <Field label="Password">
          <Input
            type="password"
            required
            minLength={isLogin ? 1 : 8}
            maxLength={128}
            autoComplete={isLogin ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        {isLogin && (
          <Link
            href="/forgot-password"
            className="-mt-2 self-end text-sm text-accent hover:underline"
          >
            Forgot password?
          </Link>
        )}
        {error && <Message kind="error">{error}</Message>}
        <Button type="submit" disabled={submitting}>
          {submitting
            ? "Please wait..."
            : isLogin
              ? "Sign in"
              : "Create account"}
        </Button>
      </form>
    </AuthShell>
  );
}
