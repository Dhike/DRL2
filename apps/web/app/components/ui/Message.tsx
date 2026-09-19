import type { ReactNode } from "react";

type Kind = "error" | "success" | "info";

const colors: Record<Kind, string> = {
  error: "text-sell",
  success: "text-buy",
  info: "text-muted",
};

export default function Message({
  kind,
  className = "",
  children,
}: {
  kind: Kind;
  className?: string;
  children: ReactNode;
}) {
  return (
    <p
      role={kind === "error" ? "alert" : "status"}
      className={`text-sm ${colors[kind]} ${className}`.trim()}
    >
      {children}
    </p>
  );
}
