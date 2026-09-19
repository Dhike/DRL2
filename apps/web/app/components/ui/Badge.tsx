import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "buy" | "sell" | "warning";

const tones: Record<Tone, string> = {
  neutral: "border-border text-muted",
  accent: "border-accent/40 bg-accent/10 text-accent",
  buy: "border-buy/40 bg-buy/10 text-buy",
  sell: "border-sell/40 bg-sell/10 text-sell",
  warning: "border-warning/40 bg-warning/10 text-warning",
};

export default function Badge({
  tone = "neutral",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
