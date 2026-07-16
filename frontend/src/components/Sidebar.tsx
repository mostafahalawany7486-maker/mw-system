import { NavLink } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Users, ShieldCheck, Building2, Globe2, MapPin, Coins,
  Settings, ClipboardList, ShieldAlert, Building, UserSquare2,
} from "lucide-react";

interface NavItem {
  label: string;
  to: string;
  icon: typeof LayoutDashboard;
  permission?: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
  { label: "Property Owners", to: "/owners", icon: UserSquare2, permission: "owners.view" },
  { label: "Users", to: "/users", icon: Users, permission: "users.view" },
  { label: "Roles & Permissions", to: "/roles", icon: ShieldCheck, permission: "roles.view" },
  { label: "Company Profile", to: "/company-profile", icon: Building, permission: "company.view" },
  { label: "Branches", to: "/branches", icon: Building2, permission: "branches.view" },
  { label: "Countries", to: "/countries", icon: Globe2, permission: "countries.view" },
  { label: "Cities", to: "/cities", icon: MapPin, permission: "cities.view" },
  { label: "Currencies", to: "/currencies", icon: Coins, permission: "currencies.view" },
  { label: "System Settings", to: "/settings", icon: Settings, permission: "settings.view" },
  { label: "Activity Log", to: "/activity-log", icon: ClipboardList },
  { label: "Audit Log", to: "/audit-log", icon: ShieldAlert, permission: "audit.view" },
];

export default function Sidebar({ collapsed }: { collapsed: boolean }) {
  const { hasPermission } = useAuth();

  return (
    <aside
      className={`hidden md:flex flex-col shrink-0 bg-ink-950 text-ink-100 transition-all duration-200 ${
        collapsed ? "w-[68px]" : "w-64"
      }`}
    >
      <div className="h-16 flex items-center gap-2 px-4 border-b border-ink-800">
        <div className="w-8 h-8 rounded-md bg-brand-500 flex items-center justify-center font-display font-bold text-ink-950 shrink-0">
          P
        </div>
        {!collapsed && <span className="font-display font-bold tracking-tight text-lg">PMS</span>}
      </div>
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {NAV_ITEMS.filter((item) => !item.permission || hasPermission(item.permission)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors relative ${
                isActive
                  ? "bg-brand-600/20 text-brand-300 before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-[3px] before:rounded-full before:bg-brand-400"
                  : "text-ink-300 hover:bg-ink-800 hover:text-white"
              }`
            }
          >
            <item.icon size={18} className="shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
