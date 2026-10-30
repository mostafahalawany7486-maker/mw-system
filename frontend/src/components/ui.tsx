import { ReactNode, useEffect, useRef, useState } from "react";
import { X, Inbox, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

// Used as the Suspense fallback for lazy-loaded routes (see Layout.tsx
// and App.tsx's route-based code splitting) — shown briefly in the main
// content area while a page chunk downloads, with Sidebar/Navbar staying
// mounted and visible throughout.
export function RouteLoadingFallback() {
  return (
    <div className="flex justify-center items-center py-24" role="status" aria-live="polite" aria-label="Loading page">
      <Loader2 className="animate-spin text-ink-400" size={26} />
    </div>
  );
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-6 gap-4 flex-wrap animate-fade-in-up">
      <div>
        <h1 className="font-display text-xl font-bold text-ink-900 dark:text-ink-50 tracking-tight">{title}</h1>
        {description && <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const cls = status === "active" ? "badge-active" : status === "pending" ? "badge-warn" : "badge-inactive";
  return (
    <span className={cls}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" aria-hidden="true" />
      {status}
    </span>
  );
}

export function Pagination({
  page, totalPages, onChange,
}: { page: number; totalPages: number; onChange: (page: number) => void }) {
  const { t } = useTranslation("common");
  if (totalPages <= 1) return null;

  // A compact page-number strip (current ±2, plus first/last with ellipses)
  // rather than prev/next-only — a small, purely presentational upgrade
  // for "Better Tables" navigation. Still just calls the same onChange(page).
  const pages: (number | "…")[] = [];
  const pageWindow = 2;
  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || (p >= page - pageWindow && p <= page + pageWindow)) {
      pages.push(p);
    } else if (pages[pages.length - 1] !== "…") {
      pages.push("…");
    }
  }

  return (
    <nav className="flex items-center justify-between px-4 py-3 border-t border-ink-100 dark:border-ink-800" aria-label="Pagination">
      <span className="text-xs text-ink-500 hidden sm:inline">{t("pagination.page")} {page} {t("pagination.of")} {totalPages}</span>
      <div className="flex gap-1 mx-auto sm:mx-0">
        <button className="btn-secondary !px-2 !py-1" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page">
          <ChevronLeft size={16} className="rtl:rotate-180" />
        </button>
        {pages.map((p, i) => p === "…" ? (
          <span key={`ellipsis-${i}`} className="w-8 h-8 flex items-center justify-center text-xs text-ink-400 select-none">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onChange(p)}
            aria-current={p === page ? "page" : undefined}
            className={`w-8 h-8 rounded-md text-xs font-medium transition-colors duration-150 ${
              p === page ? "bg-brand-600 text-white" : "text-ink-600 dark:text-ink-300 hover:bg-ink-100 dark:hover:bg-ink-800"
            }`}
          >
            {p}
          </button>
        ))}
        <button className="btn-secondary !px-2 !py-1" disabled={page >= totalPages} onClick={() => onChange(page + 1)} aria-label="Next page">
          <ChevronRight size={16} className="rtl:rotate-180" />
        </button>
      </div>
    </nav>
  );
}

export function EmptyState({ title, description, icon: Icon = Inbox }: { title: string; description?: string; icon?: typeof Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      <div className="w-12 h-12 rounded-full bg-ink-100 dark:bg-ink-800 flex items-center justify-center mb-3">
        <Icon size={20} className="text-ink-400" aria-hidden="true" />
      </div>
      <h3 className="font-medium text-ink-700 dark:text-ink-200">{title}</h3>
      {description && <p className="text-sm text-ink-400 mt-1 max-w-sm">{description}</p>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode;
}) {
  const { t } = useTranslation("common");
  const dialogRef = useRef<HTMLDivElement>(null);

  // Split into two effects on purpose. Escape-to-close needs the latest
  // `onClose` (deps: [open, onClose]) — cheap to re-subscribe, no visual
  // effect either way. Initial focus must NOT depend on `onClose`: that
  // prop is very often a fresh inline/unmemoized function on every
  // render of whatever renders this Modal, so including it here would
  // re-run `.focus()` on every keystroke inside the modal (the focus
  // moving from whatever input the person is typing in back to the
  // dialog wrapper) — exactly the "type one character, have to click
  // the field again" bug this used to cause everywhere Modal is used.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (open) dialogRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-ink-950/50 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div ref={dialogRef} tabIndex={-1} className="relative card w-full max-w-lg max-h-[85vh] flex flex-col shadow-floating animate-scale-in outline-none">
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <h3 className="font-display font-semibold">{title}</h3>
          <button className="text-ink-400 hover:text-ink-700 dark:hover:text-ink-100 rounded-md p-1 -m-1 transition-colors hover:bg-ink-100 dark:hover:bg-ink-800" onClick={onClose} aria-label={t("actions.close")}>
            <X size={18} />
          </button>
        </div>
        <div className="px-5 py-4 overflow-y-auto flex-1">{children}</div>
        {footer && <div className="px-5 py-4 border-t border-ink-100 dark:border-ink-800 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export function ToolbarSearch({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const { t } = useTranslation("common");
  return (
    <div className="relative max-w-xs w-full">
      <svg className="absolute left-3 rtl:left-auto rtl:right-3 top-1/2 -translate-y-1/2 text-ink-400 pointer-events-none" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
      </svg>
      <input
        className="input pl-8 rtl:pl-3 rtl:pr-8"
        placeholder={placeholder || t("actions.search") + "…"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={placeholder || t("actions.search")}
      />
      {value && (
        <button
          className="absolute right-2 rtl:right-auto rtl:left-2 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700 dark:hover:text-ink-200 p-0.5 rounded"
          onClick={() => onChange("")}
          aria-label={t("actions.clear")}
          type="button"
        >
          <X size={13} />
        </button>
      )}
    </div>
  );
}

// ==================== Skeleton loading states ====================
// Content-shaped loading placeholders — a more modern, less jarring
// perceived-performance pattern than a bare spinner. Purely
// presentational: pages choose to render <SkeletonCard /> etc. instead
// of <Loader2 className="animate-spin" /> while `loading` is true; the
// data-fetching logic that sets `loading` is completely untouched.
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function SkeletonText({ lines = 1, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={`h-3.5 ${i === lines - 1 && lines > 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="card p-4" aria-hidden="true">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-4 w-4 rounded-full" />
      </div>
      <Skeleton className="h-6 w-16" />
    </div>
  );
}

export function SkeletonKpiGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  );
}

export function SkeletonTable({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="card overflow-hidden" aria-busy="true" aria-label="Loading table">
      <div className="px-4 py-3 border-b border-ink-100 dark:border-ink-800 flex gap-6">
        {Array.from({ length: columns }).map((_, i) => <Skeleton key={i} className="h-3 w-16" />)}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="px-4 py-3.5 border-b border-ink-50 dark:border-ink-800/60 flex gap-6 last:border-0">
          {Array.from({ length: columns }).map((_, c) => <Skeleton key={c} className="h-3.5" style={{ width: `${40 + ((r + c) % 3) * 20}px` }} />)}
        </div>
      ))}
    </div>
  );
}

// ==================== Form field wrapper ====================
// Standardizes label + input + hint/error rendering for "Better Forms".
// Existing forms that build their own <label className="label"> +
// <input className="input"> by hand keep working exactly as before —
// this is an additional, opt-in primitive for new/updated forms, not a
// replacement that every existing form was rewritten to use.
export function FormField({
  label, htmlFor, error, hint, required, children,
}: { label: string; htmlFor?: string; error?: string; hint?: string; required?: boolean; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="label">
        {label}{required && <span className="text-rust-500 ml-0.5" aria-hidden="true">*</span>}
      </label>
      {children}
      {error ? (
        <p className="text-xs text-rust-500 mt-1.5" role="alert">{error}</p>
      ) : hint ? (
        <p className="text-xs text-ink-400 mt-1.5">{hint}</p>
      ) : null}
    </div>
  );
}

// ==================== Tooltip ====================
// Used for icon-only affordances (e.g. the collapsed Sidebar) where a
// visible label isn't shown — improves both discoverability and
// accessibility (the tooltip text doubles as an accessible name hint).
export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative inline-flex" onMouseEnter={() => setVisible(true)} onMouseLeave={() => setVisible(false)} onFocus={() => setVisible(true)} onBlur={() => setVisible(false)}>
      {children}
      {visible && (
        <span
          role="tooltip"
          className="absolute left-full rtl:left-auto rtl:right-full ml-2 rtl:ml-0 rtl:mr-2 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-md bg-ink-900 dark:bg-ink-700 text-white text-xs px-2 py-1 shadow-floating z-50 animate-fade-in pointer-events-none"
        >
          {label}
        </span>
      )}
    </div>
  );
}
