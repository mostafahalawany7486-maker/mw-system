import { useState } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/context/AuthContext";
import { Tooltip } from "@/components/ui";
import {
  LayoutDashboard, Users, ShieldCheck, Building2, Globe2, MapPin, Coins,
  Settings, ClipboardList, ShieldAlert, Building, UserSquare2, FileText, Home, UsersRound, FileSignature, Wallet, Wrench, Calculator, BarChart3, LayoutGrid, X, CalendarClock, FileStack, ChevronDown,
} from "lucide-react";

interface NavItem {
  labelKey: string;
  to: string;
  icon: typeof LayoutDashboard;
  permission?: string;
  // Module color-coding: a full, literal Tailwind class per item (not
  // built via string interpolation — Tailwind's JIT content scanner
  // only picks up complete class-name strings that actually appear in
  // the source, so these have to be spelled out, not assembled from a
  // short color name at runtime).
  iconColor: string;
  chipBg: string;
  // "primary" = the 9 essential modules the business actually runs on
  // day to day (Dashboard, Owners, Properties, Master Leases, Tenants,
  // Contracts, Rent Collection, Maintenance, Reports) — always visible.
  // "secondary" = setup/admin/back-office items, still one click away
  // under "Settings & Admin" below, never deleted or hidden entirely —
  // same "collapse, don't remove" approach already used for
  // Currencies/Countries.
  group: "primary" | "secondary";
}

const NAV_ITEMS: NavItem[] = [
  { labelKey: "dashboard", to: "/dashboard", icon: LayoutDashboard, iconColor: "text-brand-400", chipBg: "bg-brand-500/15", group: "primary" },
  { labelKey: "propertyOwners", to: "/owners", icon: UserSquare2, permission: "owners.view", iconColor: "text-violet-400", chipBg: "bg-violet-500/15", group: "primary" },
  { labelKey: "properties", to: "/properties", icon: Home, permission: "properties.view", iconColor: "text-sky-400", chipBg: "bg-sky-500/15", group: "primary" },
  { labelKey: "leaseAgreements", to: "/leases", icon: FileText, permission: "leases.view", iconColor: "text-indigo-400", chipBg: "bg-indigo-500/15", group: "primary" },
  { labelKey: "tenants", to: "/tenants", icon: UsersRound, permission: "tenants.view", iconColor: "text-rose-400", chipBg: "bg-rose-500/15", group: "primary" },
  { labelKey: "rentalContracts", to: "/rentals", icon: FileSignature, permission: "rentals.view", iconColor: "text-fuchsia-400", chipBg: "bg-fuchsia-500/15", group: "primary" },
  { labelKey: "payments", to: "/payments/collect-rent", icon: Wallet, permission: "payments.view", iconColor: "text-emerald-400", chipBg: "bg-emerald-500/15", group: "primary" },
  { labelKey: "maintenance", to: "/maintenance", icon: Wrench, permission: "maintenance.view", iconColor: "text-orange-400", chipBg: "bg-orange-500/15", group: "primary" },
  { labelKey: "reports", to: "/reports", icon: BarChart3, permission: "reports.view", iconColor: "text-blue-400", chipBg: "bg-blue-500/15", group: "primary" },

  { labelKey: "rentCycles", to: "/rent-cycles", icon: CalendarClock, permission: "rent_cycles.view", iconColor: "text-cyan-400", chipBg: "bg-cyan-500/15", group: "secondary" },
  { labelKey: "rentVouchers", to: "/rent-vouchers", icon: FileStack, permission: "rent_vouchers.view", iconColor: "text-teal-400", chipBg: "bg-teal-500/15", group: "secondary" },
  { labelKey: "financial", to: "/financial", icon: Wallet, permission: "financial.view", iconColor: "text-green-400", chipBg: "bg-green-500/15", group: "secondary" },
  { labelKey: "accounting", to: "/accounting", icon: Calculator, permission: "accounting.view", iconColor: "text-amber-400", chipBg: "bg-amber-500/15", group: "secondary" },
  { labelKey: "users", to: "/users", icon: Users, permission: "users.view", iconColor: "text-purple-400", chipBg: "bg-purple-500/15", group: "secondary" },
  { labelKey: "rolesPermissions", to: "/roles", icon: ShieldCheck, permission: "roles.view", iconColor: "text-pink-400", chipBg: "bg-pink-500/15", group: "secondary" },
  { labelKey: "companyProfile", to: "/company-profile", icon: Building, permission: "company.view", iconColor: "text-stone-400", chipBg: "bg-stone-500/15", group: "secondary" },
  { labelKey: "branches", to: "/branches", icon: Building2, permission: "branches.view", iconColor: "text-yellow-400", chipBg: "bg-yellow-500/15", group: "secondary" },
  { labelKey: "cities", to: "/cities", icon: MapPin, permission: "cities.view", iconColor: "text-lime-400", chipBg: "bg-lime-500/15", group: "secondary" },
  { labelKey: "systemSettings", to: "/settings", icon: Settings, permission: "settings.view", iconColor: "text-slate-400", chipBg: "bg-slate-500/15", group: "secondary" },
  { labelKey: "activityLog", to: "/activity-log", icon: ClipboardList, iconColor: "text-zinc-400", chipBg: "bg-zinc-500/15", group: "secondary" },
  { labelKey: "auditLog", to: "/audit-log", icon: ShieldAlert, permission: "audit.view", iconColor: "text-red-400", chipBg: "bg-red-500/15", group: "secondary" },
];

function NavLinks({ items, collapsed, t, onNavigate }: { items: NavItem[]; collapsed: boolean; t: (k: string) => string; onNavigate?: () => void }) {
  return (
    <>
      {items.map((item) => {
        const link = (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-150 relative ${
                isActive
                  ? "bg-brand-600/20 text-brand-300 before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-[3px] before:rounded-full before:bg-brand-400"
                  : "text-ink-300 hover:bg-ink-800 hover:text-white hover:translate-x-0.5"
              }`
            }
          >
            <span className={`shrink-0 rounded-md p-1.5 transition-transform duration-150 group-hover:scale-110 ${item.chipBg}`}>
              <item.icon size={15} className={item.iconColor} />
            </span>
            {!collapsed && <span className="animate-fade-in">{t(item.labelKey)}</span>}
          </NavLink>
        );
        return collapsed ? <Tooltip key={item.to} label={t(item.labelKey)}>{link}</Tooltip> : link;
      })}
    </>
  );
}

function SecondaryNavSection({
  items, collapsed, open, onToggle, t, onNavigate,
}: { items: NavItem[]; collapsed: boolean; open: boolean; onToggle: () => void; t: (k: string) => string; onNavigate?: () => void }) {
  if (items.length === 0) return null;

  // Collapsed rail: no room for a "Settings & Admin" label, so the
  // secondary items are simply always shown (still one click, just
  // without the toggle affordance collapsed-mode has no space for).
  if (collapsed) {
    return <NavLinks items={items} collapsed={collapsed} t={t} onNavigate={onNavigate} />;
  }

  return (
    <div className="pt-2 mt-2 border-t border-ink-800">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wide text-ink-500 hover:text-ink-300"
      >
        {t("settingsAndAdmin")}
        <ChevronDown size={14} className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-0.5 animate-fade-in">
          <NavLinks items={items} collapsed={false} t={t} onNavigate={onNavigate} />
        </div>
      )}
    </div>
  );
}

function Logo({ collapsed }: { collapsed: boolean }) {
  return (
    <div className="h-16 flex items-center gap-2.5 px-4 border-b border-ink-800 shrink-0">
      <div className="w-8 h-8 rounded-md bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center font-display font-bold text-white shrink-0 shadow-sm">
        P
      </div>
      {!collapsed && <span className="font-display font-bold tracking-tight text-lg animate-fade-in">PMS</span>}
    </div>
  );
}

export default function Sidebar({ collapsed, mobileOpen = false, onCloseMobile }: { collapsed: boolean; mobileOpen?: boolean; onCloseMobile?: () => void }) {
  const { hasPermission } = useAuth();
  const { t } = useTranslation("nav");
  const [secondaryOpen, setSecondaryOpen] = useState(false);

  const visibleItems = NAV_ITEMS.filter((item) => !item.permission || hasPermission(item.permission));
  const primaryItems = visibleItems.filter((i) => i.group === "primary");
  const secondaryItems = visibleItems.filter((i) => i.group === "secondary");

  return (
    <>
      {/* Desktop: persistent, collapsible sidebar (unchanged behavior) */}
      <aside
        className={`hidden md:flex flex-col shrink-0 bg-ink-950 text-ink-100 transition-[width] duration-200 ease-out-expo ${
          collapsed ? "w-[68px]" : "w-64"
        }`}
      >
        <Logo collapsed={collapsed} />
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5" aria-label="Primary">
          <NavLinks items={primaryItems} collapsed={collapsed} t={t} />
          <SecondaryNavSection items={secondaryItems} collapsed={collapsed} open={secondaryOpen} onToggle={() => setSecondaryOpen((v) => !v)} t={t} />
        </nav>
      </aside>

      {/* Mobile: overlay drawer, opened via the Navbar's hamburger button.
          This completes an affordance that already existed (the button
          was already wired to onToggleSidebar) but previously had no
          effect below the md breakpoint, since the sidebar was
          unconditionally hidden there — a genuine responsive-design gap,
          not a new feature. */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-ink-950/60 backdrop-blur-sm animate-fade-in" onClick={onCloseMobile} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 rtl:left-auto rtl:right-0 w-72 max-w-[80vw] bg-ink-950 text-ink-100 flex flex-col shadow-floating animate-slide-in-right rtl:animate-none">
            <div className="flex items-center justify-between">
              <Logo collapsed={false} />
              <button className="text-ink-400 hover:text-white p-2 mr-2" onClick={onCloseMobile} aria-label={t("closeMenu")}>
                <X size={18} />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5" aria-label="Primary">
              <NavLinks items={primaryItems} collapsed={false} t={t} onNavigate={onCloseMobile} />
              <SecondaryNavSection items={secondaryItems} collapsed={false} open={secondaryOpen} onToggle={() => setSecondaryOpen((v) => !v)} t={t} onNavigate={onCloseMobile} />
            </nav>
          </aside>
        </div>
      )}
    </>
  );
}
