import { useState, useEffect, useRef } from "react";
import { Menu, Sun, Moon, Bell, Search, LogOut, User as UserIcon, ChevronDown } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { NotificationItem } from "@/types";

export default function Navbar({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiClient.get("/notifications/unread-count").then(({ data }) => setUnreadCount(data.unread_count)).catch(() => {});
  }, []);

  const openNotifications = async () => {
    setNotifOpen((v) => !v);
    if (!notifOpen) {
      const { data } = await apiClient.get<NotificationItem[]>("/notifications");
      setNotifications(data);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <header className="h-16 shrink-0 flex items-center gap-4 px-4 md:px-6 border-b border-ink-100 dark:border-ink-800 bg-white dark:bg-ink-900">
      <button className="btn-secondary !px-2" onClick={onToggleSidebar} aria-label="Toggle sidebar">
        <Menu size={18} />
      </button>

      <div className="flex-1 max-w-md relative hidden sm:block">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
        <input className="input pl-9" placeholder="Search anything…" aria-label="Global search" />
      </div>

      <div className="flex-1 sm:hidden" />

      <button className="btn-secondary !px-2" onClick={toggleTheme} aria-label="Toggle theme">
        {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
      </button>

      <div className="relative">
        <button className="btn-secondary !px-2 relative" onClick={openNotifications} aria-label="Notifications">
          <Bell size={18} />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-rust-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>
        {notifOpen && (
          <div className="absolute right-0 mt-2 w-80 card p-2 z-20 max-h-96 overflow-y-auto">
            <div className="px-2 py-1.5 text-xs font-semibold uppercase text-ink-400">Notifications</div>
            {notifications.length === 0 && <div className="px-2 py-4 text-sm text-ink-400 text-center">No notifications yet</div>}
            {notifications.map((n) => (
              <div key={n.id} className={`px-2 py-2 rounded-md text-sm ${!n.is_read ? "bg-brand-50 dark:bg-brand-900/20" : ""}`}>
                <div className="font-medium">{n.title}</div>
                <div className="text-ink-500 dark:text-ink-400 text-xs mt-0.5">{n.message}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="relative" ref={menuRef}>
        <button
          className="flex items-center gap-2 rounded-md pl-1 pr-2 py-1 hover:bg-ink-50 dark:hover:bg-ink-800"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <div className="w-8 h-8 rounded-full bg-brand-600 text-white flex items-center justify-center text-sm font-semibold">
            {user?.first_name?.[0]}
            {user?.last_name?.[0]}
          </div>
          <span className="hidden sm:block text-sm font-medium">{user?.first_name} {user?.last_name}</span>
          <ChevronDown size={14} className="text-ink-400" />
        </button>
        {menuOpen && (
          <div className="absolute right-0 mt-2 w-48 card p-1 z-20">
            <div className="px-3 py-2 text-xs text-ink-400 border-b border-ink-100 dark:border-ink-800 mb-1">{user?.email}</div>
            <button className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md hover:bg-ink-50 dark:hover:bg-ink-800">
              <UserIcon size={15} /> My Profile
            </button>
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md text-rust-500 hover:bg-rust-50 dark:hover:bg-rust-500/10"
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
