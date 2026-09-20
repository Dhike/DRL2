"use client";

import { Moon, Sun } from "lucide-react";

import { setTheme, useTheme } from "../lib/theme";

export default function ThemeToggle() {
  const theme = useTheme();

  return (
    <button
      type="button"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label={
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
      }
      className="rounded-lg p-2 text-muted hover:bg-surface-hover hover:text-foreground"
    >
      {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
