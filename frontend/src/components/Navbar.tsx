import { useState, useEffect, useRef } from "react";
import { Menu, Sun, Moon, Bell, Search, LogOut, User as UserIcon, ChevronDown, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { NotificationItem } from "@/types";
import LanguageSwitcher from "@/components/LanguageSwitcher";

const SEARCH_CATEGORY_LABELS: Record<string, string> = {
  buildings_units: "Buildings & Units", tenants: "Tenants", owners: "Owners", contracts: "Contracts",
  receipts: "Receipts", expenses: "Expenses", maintenance: "Maintenance", payments: "Payments",
};

export default function Navbar({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const { theme, toggleTheme } = useTheme();
  const { t } = useTranslation("common");
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  // Global Search (Executive Dashboard Phase 3)
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Record<string, Array<{ id: number; label: string; link: string }>>>({});
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (searchQuery.trim().length < 2) { setSearchResults({}); setSearchOpen(false); return; }
    setSearchLoading(true);
    setSearchOpen(true);
    const handle = setTimeout(() => {
      apiClient.get("/search", { params: { q: searchQuery } })
        .then(({ data }) => setSearchResults(data.results || {}))
        .catch(() => setSearchResults({}))
        .finally(() => setSearchLoading(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [searchQuery]);

  useEffect(() => {
    apiClient.get("/notifications/unread-count").then(({ data }) => setUnreadCount(data.unread_count)).catch(() => {});
  }, []);

  // menuRef was already declared and attached to the user-menu dropdown,
  // but nothing ever actually closed it on an outside click — found
  // during the production audit. Mirrors the exact pattern already
  // working correctly in LanguageSwitcher.tsx.
  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setSearchOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const openNotifications = async () => {
    setNotifOpen((v) => !v);
    if (!notifOpen) {
      const { data } = await apiClient.get<NotificationItem[]>("/notifications");
      setNotifications(data);
      // Opening the panel is what "reading" them means here — this was
      // previously never called at all, so the unread badge stayed
      // stuck at whatever it was on page load, forever, even after
      // scrolling through every notification. Mirrors what the bell
      // icon visually implies happens.
      if (data.some((n) => !n.is_read)) {
        await apiClient.post("/notifications/read-all").catch(() => {});
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
        setUnreadCount(0);
      }
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <header className="h-16 shrink-0 flex items-center gap-4 px-4 md:px-6 border-b border-ink-100 dark:border-ink-800 bg-white/80 dark:bg-ink-900/80 backdrop-blur-sm sticky top-0 z-30">
      <button className="btn-secondary !px-2" onClick={onToggleSidebar} aria-label="Toggle sidebar">
        <Menu size={18} />
      </button>

      <div className="flex-1 max-w-md relative hidden sm:block" ref={searchRef}>
        <Search size={16} className="absolute left-3 rtl:left-auto rtl:right-3 top-1/2 -translate-y-1/2 text-ink-400" />
        <input
          className="input pl-9 rtl:pl-3 rtl:pr-9"
          placeholder={t("messages.searchPlaceholder")}
          aria-label="Global search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => searchQuery.length >= 2 && setSearchOpen(true)}
        />
        {searchOpen && (
          <div className="absolute left-0 rtl:left-auto rtl:right-0 mt-2 w-full min-w-[22rem] card shadow-floating p-2 z-30 max-h-[28rem] overflow-y-auto animate-scale-in">
            {searchLoading && <div className="px-2 py-3 text-xs text-ink-400 flex items-center gap-1.5"><Loader2 size={12} className="animate-spin" /> Searching…</div>}
            {!searchLoading && Object.keys(searchResults).length === 0 && (
              <div className="px-2 py-3 text-xs text-ink-400">No results for "{searchQuery}"</div>
            )}
            {!searchLoading && Object.entries(searchResults).map(([category, items]) => (
              <div key={category} className="mb-1.5 last:mb-0">
                <div className="px-2 py-1 text-[10px] font-semibold uppercase text-ink-400">{SEARCH_CATEGORY_LABELS[category] || category}</div>
                {items.map((item) => (
                  <button
                    key={item.id}
                    className="w-full text-left px-2 py-1.5 text-sm rounded-md hover:bg-ink-50 dark:hover:bg-ink-800/60 truncate"
                    onClick={() => { navigate(item.link); setSearchOpen(false); setSearchQuery(""); }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex-1 sm:hidden" />

      <LanguageSwitcher />

      <button className="btn-secondary !px-2 overflow-hidden" onClick={toggleTheme} aria-label={theme === "light" ? t("theme.toggleDark") : t("theme.toggleLight")}>
        <span className="inline-block transition-transform duration-300" key={theme}>
          {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
        </span>
      </button>

      <div className="relative" ref={notifRef}>
        <button className="btn-secondary !px-2 relative" onClick={openNotifications} aria-label="Notifications" aria-expanded={notifOpen}>
          <Bell size={18} />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 rtl:-right-auto rtl:-left-1 bg-rust-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center animate-scale-in ring-2 ring-white dark:ring-ink-900">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>
        {notifOpen && (
          <div className="absolute right-0 rtl:right-auto rtl:left-0 mt-2 w-80 card shadow-floating p-2 z-20 max-h-96 overflow-y-auto animate-scale-in origin-top-right rtl:origin-top-left">
            <div className="px-2 py-1.5 text-xs font-semibold uppercase text-ink-400">Notifications</div>
            {notifications.length === 0 && <div className="px-2 py-4 text-sm text-ink-400 text-center">{t("messages.noResults")}</div>}
            {notifications.map((n) => (
              <div key={n.id} className={`px-2 py-2 rounded-md text-sm transition-colors ${!n.is_read ? "bg-brand-50 dark:bg-brand-900/20" : "hover:bg-ink-50 dark:hover:bg-ink-800/60"}`}>
                <div className="font-medium">{n.title}</div>
                <div className="text-ink-500 dark:text-ink-400 text-xs mt-0.5">{n.message}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="relative" ref={menuRef}>
        <button
          className="flex items-center gap-2 rounded-md pl-1 pr-2 py-1 hover:bg-ink-50 dark:hover:bg-ink-800 transition-colors"
          onClick={() => setMenuOpen((v) => !v)}
          aria-expanded={menuOpen}
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-white flex items-center justify-center text-sm font-semibold shadow-sm">
            {user?.first_name?.[0]}
            {user?.last_name?.[0]}
          </div>
          <span className="hidden sm:block text-sm font-medium">{user?.first_name} {user?.last_name}</span>
          <ChevronDown size={14} className={`text-ink-400 transition-transform duration-200 ${menuOpen ? "rotate-180" : ""}`} />
        </button>
        {menuOpen && (
          <div className="absolute right-0 rtl:right-auto rtl:left-0 mt-2 w-48 card shadow-floating p-1 z-20 animate-scale-in origin-top-right rtl:origin-top-left">
            <div className="px-3 py-2 text-xs text-ink-400 border-b border-ink-100 dark:border-ink-800 mb-1 truncate">{user?.email}</div>
            <button className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md hover:bg-ink-50 dark:hover:bg-ink-800 transition-colors">
              <UserIcon size={15} /> My Profile
            </button>
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md text-rust-500 hover:bg-rust-50 dark:hover:bg-rust-500/10 transition-colors"
              onClick={handleLogout}
            >
              <LogOut size={15} /> Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
