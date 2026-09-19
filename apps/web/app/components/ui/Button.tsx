import type { ButtonHTMLAttributes } from "react";

type SolidVariant = "primary" | "secondary" | "danger";
type Variant = SolidVariant | "link";

const base =
  "inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const solid: Record<SolidVariant, string> = {
  primary: "bg-accent text-accent-foreground hover:bg-accent-hover",
  secondary: "border border-border bg-surface hover:bg-surface-hover",
  danger: "border border-sell/40 text-sell hover:bg-sell/10",
};

export function buttonClass(variant: Variant = "primary", extra = ""): string {
  if (variant === "link") {
    return `text-sm text-accent hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline ${extra}`.trim();
  }
  return `${base} ${solid[variant]} ${extra}`.trim();
}

export default function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button {...props} className={buttonClass(variant, className)} />;
}
