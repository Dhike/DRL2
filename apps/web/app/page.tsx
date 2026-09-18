"use client";

import { useEffect, useState } from "react";

type Health = { status: string; service: string; environment: string };

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  let statusText = "Checking API...";
  if (health) statusText = `API: ${health.status} (${health.environment})`;
  else if (error) statusText = `API unreachable: ${error}`;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold">DRL2</h1>
      <p className="text-sm opacity-70">Trading platform foundation</p>
      <div className="rounded-lg border border-current/20 px-4 py-3 text-sm">
        {statusText}
      </div>
    </main>
  );
}
