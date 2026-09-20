import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "drl2_theme";

function subscribe(callback: () => void) {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}

function getSnapshot(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function getServerSnapshot(): Theme {
  return "dark";
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* storage unavailable: the choice lasts until reload */
  }
}
