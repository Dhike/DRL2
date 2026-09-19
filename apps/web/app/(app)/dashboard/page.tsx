"use client";

import { useEffect, useState } from "react";

import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import { useUser } from "../../components/UserContext";
import { API_BASE_URL } from "../../lib/api";

type Health = { status: string; service: string; environment: string };

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

  let apiBadge = <Badge>Checking...</Badge>;
  let apiDetail = "Contacting the server";
  if (health) {
    apiBadge = <Badge tone="buy">Online</Badge>;
    apiDetail = `Environment: ${health.environment}`;
  } else if (healthError) {
    apiBadge = <Badge tone="sell">Unreachable</Badge>;
    apiDetail = healthError;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-1 text-sm text-muted">Welcome back, {user.email}</p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Card title="API status">
          {apiBadge}
          <p className="mt-2 text-sm text-muted">{apiDetail}</p>
        </Card>
        <Card title="Account">
          <p className="truncate text-sm">{user.email}</p>
          <div className="mt-2">
            <Badge tone="accent">{user.role}</Badge>
          </div>
        </Card>
        <Card title="Market data">
          <Badge tone="warning">Not connected</Badge>
          <p className="mt-2 text-sm text-muted">
            The first data provider arrives in Phase 4.
          </p>
        </Card>
        <Card title="Scanner">
          <Badge>Idle</Badge>
          <p className="mt-2 text-sm text-muted">
            Automatic scanning arrives in Phase 8.
          </p>
        </Card>
      </div>
    </div>
  );
}
