"use client";

import { useEffect, useState, type ReactNode } from "react";

import { useUser } from "../../components/UserContext";
import { API_BASE_URL } from "../../lib/api";

type Health = { status: string; service: string; environment: string };

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-current/15 p-4">
      <h2 className="text-xs font-medium uppercase tracking-wide opacity-60">
        {title}
      </h2>
      <div className="mt-2 text-sm">{children}</div>
    </div>
  );
}

export default function DashboardPage() {
  const user = useUser();
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((err: Error) => setHealthError(err.message));
  }, []);

  let apiText = "Checking...";
  if (health) apiText = `Online (${health.environment})`;
  else if (healthError) apiText = `Unreachable: ${healthError}`;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-1 text-sm opacity-70">Welcome back, {user.email}</p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Card title="API status">{apiText}</Card>
        <Card title="Account">
          {user.email}
          <span className="block opacity-60">Role: {user.role}</span>
        </Card>
        <Card title="Market data">
          Not connected yet
          <span className="block opacity-60">
            The first data provider arrives in Phase 4.
          </span>
        </Card>
        <Card title="Scanner">
          No scans yet
          <span className="block opacity-60">
            Automatic scanning arrives in Phase 8.
          </span>
        </Card>
      </div>
    </div>
  );
}
