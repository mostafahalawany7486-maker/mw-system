import { ReactNode } from "react";
import { X, Inbox, ChevronLeft, ChevronRight } from "lucide-react";

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
      <div>
        <h1 className="font-display text-xl font-bold text-ink-900 dark:text-ink-50">{title}</h1>
        {description && <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const cls = status === "active" ? "badge-active" : status === "pending" ? "badge-warn" : "badge-inactive";
  return <span className={cls}>{status}</span>;
}

export function Pagination({
  page, totalPages, onChange,
}: { page: number; totalPages: number; onChange: (page: number) => void }) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-ink-100 dark:border-ink-800">
      <span className="text-xs text-ink-500">Page {page} of {totalPages}</span>
      <div className="flex gap-1">
        <button className="btn-secondary !px-2 !py-1" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          <ChevronLeft size={16} />
        </button>
        <button className="btn-secondary !px-2 !py-1" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-ink-100 dark:bg-ink-800 flex items-center justify-center mb-3">
        <Inbox size={20} className="text-ink-400" />
      </div>
      <h3 className="font-medium text-ink-700 dark:text-ink-200">{title}</h3>
      {description && <p className="text-sm text-ink-400 mt-1 max-w-sm">{description}</p>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink-950/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative card w-full max-w-lg max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <h3 className="font-display font-semibold">{title}</h3>
          <button className="text-ink-400 hover:text-ink-700 dark:hover:text-ink-100" onClick={onClose} aria-label="Close">
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
  return (
    <input
      className="input max-w-xs"
      placeholder={placeholder || "Search…"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
