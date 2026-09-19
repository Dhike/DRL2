"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { getMe, type User } from "../lib/api";
import { NAV_ITEMS } from "../lib/nav";
import Avatar from "./Avatar";
import ThemeToggle from "./ThemeToggle";
import { UserProvider } from "./UserContext";

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) router.replace("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm opacity-70">
        Loading...
      </div>
    );
  }

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(`${href}/`);

  return (
    <UserProvider value={user}>
      <div className="min-h-screen md:flex">
        <aside className="hidden w-60 shrink-0 flex-col border-r border-current/10 p-4 md:flex">
          <div className="mb-6 px-2 text-xl font-semibold">DRL2</div>
          <nav className="flex flex-1 flex-col gap-1">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                  isActive(href)
                    ? "bg-current/10 font-medium"
                    : "opacity-70 hover:bg-current/5"
                }`}
              >
                <Icon size={18} />
                {label}
              </Link>
            ))}
          </nav>
        </aside>

        <div className="flex min-h-screen flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-current/10 px-4 py-3">
            <span className="text-lg font-semibold md:hidden">DRL2</span>
            <span className="hidden text-sm opacity-70 md:block">
              Analysis only. No live trading is enabled.
            </span>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Link
                href="/account"
                aria-label="Account"
                className="rounded-full ring-1 ring-current/20 hover:ring-current/50"
              >
                <Avatar size={36} />
              </Link>
            </div>
          </header>
          <main className="flex-1 p-4 pb-24 md:p-8 md:pb-8">{children}</main>
        </div>

        <nav className="fixed inset-x-0 bottom-0 flex justify-around border-t border-current/10 bg-background py-2 md:hidden">
          {NAV_ITEMS.map(({ href, short, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`flex flex-col items-center gap-1 px-2 text-[10px] ${
                isActive(href) ? "font-medium" : "opacity-60"
              }`}
            >
              <Icon size={20} />
              {short}
            </Link>
          ))}
        </nav>
      </div>
    </UserProvider>
  );
}
