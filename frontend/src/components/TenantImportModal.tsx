import { useState, useRef } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Download, Upload, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

interface ImportError { row: number; message: string; }
interface ImportResult { created_count: number; tenants: { id: number; tenant_code: string; display_name: string }[]; }

export default function TenantImportModal({
  open, onClose, buildingId, buildingTitle, onImported,
}: { open: boolean; onClose: () => void; buildingId: number; buildingTitle: string; onImported: () => void }) {
  const [downloading, setDownloading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [errors, setErrors] = useState<ImportError[] | null>(null);
  const [genericError, setGenericError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = () => { setErrors(null); setGenericError(null); setResult(null); };

  const handleClose = () => { reset(); onClose(); };

  const downloadTemplate = async () => {
    setDownloading(true);
    try {
      const { data, headers } = await apiClient.get(`/tenants/import-template/${buildingId}`, { responseType: "blob" });
      const contentType = typeof headers["content-type"] === "string" ? headers["content-type"] : undefined;
      const blob = new Blob([data], { type: contentType });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const disposition: string = headers["content-disposition"] || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      link.download = match ? match[1] : `tenant-import-${buildingId}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const handleFileChosen = async (file: File) => {
    reset();
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await apiClient.post<ImportResult>(`/tenants/import/${buildingId}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
      onImported();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail && typeof detail === "object" && Array.isArray(detail.errors)) {
        setErrors(detail.errors);
        setGenericError(detail.message);
      } else {
        setGenericError(typeof detail === "string" ? detail : "Import failed — please check the file and try again.");
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <Modal open={open} onClose={handleClose} title={`Import Tenants — ${buildingTitle}`} footer={<button className="btn-secondary" onClick={handleClose}>Close</button>}>
      <div className="space-y-5">
        <div className="rounded-lg border border-ink-100 dark:border-ink-800 p-4">
          <p className="text-sm font-medium mb-1">Step 1 — Download the template</p>
          <p className="text-xs text-ink-400 mb-3">
            An Excel file listing every unit already recorded for this building, one row each, ready for you to fill in tenant details next to each one.
          </p>
          <button className="btn-secondary" onClick={downloadTemplate} disabled={downloading}>
            {downloading ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Download Template (.xlsx)
          </button>
        </div>

        <div className="rounded-lg border border-ink-100 dark:border-ink-800 p-4">
          <p className="text-sm font-medium mb-1">Step 2 — Upload the filled file</p>
          <p className="text-xs text-ink-400 mb-3">
            Every row is checked first — if anything is wrong, nothing is created and you'll get an exact list of what to fix, row by row.
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFileChosen(e.target.files[0])}
          />
          <button className="btn-primary" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} Upload Filled File
          </button>
        </div>

        {result && (
          <div className="flex items-start gap-2 text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 rounded-md px-3 py-2.5">
            <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">{result.created_count} tenant(s) created successfully.</p>
              <p className="text-xs text-ink-400 mt-1">
                {result.tenants.map((t) => t.display_name).join(", ")}. They now appear in the main Tenants list — link each to a rental contract for a specific unit whenever you're ready.
              </p>
            </div>
          </div>
        )}

        {genericError && !errors && (
          <div className="flex items-start gap-2 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2.5">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span>{genericError}</span>
          </div>
        )}

        {errors && errors.length > 0 && (
          <div className="rounded-md border border-rust-200 dark:border-rust-500/30 overflow-hidden">
            <div className="flex items-start gap-2 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 px-3 py-2.5">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <span>{genericError || `${errors.length} row(s) need fixing — nothing was imported yet.`}</span>
            </div>
            <div className="max-h-56 overflow-y-auto divide-y divide-ink-100 dark:divide-ink-800">
              {errors.map((e, i) => (
                <div key={i} className="px-3 py-2 text-xs flex gap-2">
                  <span className="font-mono text-ink-400 shrink-0">Row {e.row}</span>
                  <span>{e.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
