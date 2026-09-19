import type { ReactNode } from "react";

import ThemeToggle from "../ThemeToggle";

export default function AuthShell({
  title,
  subtitle,
  footer,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div className="text-center">
        <div className="mb-3 text-sm font-semibold tracking-widest text-accent">
          DRL2
        </div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {subtitle && <p className="mt-2 text-sm text-muted">{subtitle}</p>}
      </div>
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-5 shadow-sm">
        {children}
      </div>
      {footer && <div className="text-sm text-muted">{footer}</div>}
    </main>
  );
}
