"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { API_BASE_URL, clearToken, getMe, type User } from "./lib/api";

type Health = { status: string; service: string; environment: string };

type Session =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; user: User };

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [session, setSession] = useState<Session>({ status: "loading" });

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((err: Error) => setHealthError(err.message));
  }, []);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((user) => {
        if (!cancelled) setSession({ status: "signed-in", user });
      })
      .catch(() => {
        if (!cancelled) setSession({ status: "signed-out" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleLogout() {
    clearToken();
    setSession({ status: "signed-out" });
  }

  let apiText = "Checking API...";
  if (health) apiText = `API: ${health.status} (${health.environment})`;
  else if (healthError) apiText = `API unreachable: ${healthError}`;

  const boxClass = "rounded-lg border border-current/20 px-4 py-3 text-sm";

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold">DRL2</h1>
      <p className="text-sm opacity-70">Trading platform foundation</p>
      <div className={boxClass}>{apiText}</div>

      {session.status === "loading" && (
        <div className={boxClass}>Checking session...</div>
      )}

      {session.status === "signed-out" && (
        <div className={`${boxClass} flex gap-4`}>
          <Link href="/login" className="underline">
            Sign in
          </Link>
          <Link href="/register" className="underline">
            Create account
          </Link>
        </div>
      )}

      {session.status === "signed-in" && (
        <div className={`${boxClass} flex flex-col items-center gap-2`}>
          <span>Signed in as {session.user.email}</span>
          <span className="opacity-70">Role: {session.user.role}</span>
          <button
            type="button"
            onClick={handleLogout}
            className="underline"
          >
            Log out
          </button>
        </div>
      )}
    </main>
  );
}
