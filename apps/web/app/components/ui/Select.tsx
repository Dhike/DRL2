import type { SelectHTMLAttributes } from "react";

export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent focus:ring-1 focus:ring-accent disabled:opacity-50 ${className}`.trim()}
    />
  );
}
