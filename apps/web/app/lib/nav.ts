import {
  Activity,
  Bot,
  History,
  LayoutDashboard,
  Search,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  short: string;
  icon: LucideIcon;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", short: "Home", icon: LayoutDashboard },
  { href: "/manual-analysis", label: "Manual Analysis", short: "Analysis", icon: Activity },
  { href: "/scanner", label: "Scanner", short: "Scanner", icon: Search },
  { href: "/automated", label: "Automated Trading", short: "Auto", icon: Bot },
  { href: "/trades", label: "Trades", short: "Trades", icon: History },
  { href: "/settings", label: "Settings", short: "Settings", icon: Settings },
];
