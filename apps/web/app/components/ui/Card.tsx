import type { ReactNode } from "react";

export default function Card({
  title,
  className = "",
  children,
}: {
  title?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={`rounded-xl border border-border bg-surface p-4 ${className}`.trim()}
    >
      {title && (
        <h2 className="text-xs font-medium uppercase tracking-wide text-muted">
          {title}
        </h2>
      )}
      <div className={title ? "mt-3" : ""}>{children}</div>
    </section>
  );
}
