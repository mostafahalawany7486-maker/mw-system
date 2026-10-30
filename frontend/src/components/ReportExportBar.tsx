import { useState } from "react";
import { useTranslation } from "react-i18next";
import { FileDown, FileSpreadsheet, FileText, Printer, Loader2 } from "lucide-react";
import apiClient from "@/api/client";

interface Props {
  reportType: string;
  filters?: Record<string, string | number | boolean | undefined>;
}

export default function ReportExportBar({ reportType, filters }: Props) {
  const { t } = useTranslation("common");
  const [downloading, setDownloading] = useState<"pdf" | "excel" | "csv" | null>(null);

  const download = async (format: "pdf" | "excel" | "csv") => {
    setDownloading(format);
    try {
      const { data, headers } = await apiClient.get(`/reports/${reportType}/export`, {
        params: { ...filters, format },
        responseType: "blob",
      });
      const blob = new Blob([data], { type: headers["content-type"] });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const disposition: string = headers["content-disposition"] || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const ext = format === "pdf" ? "pdf" : format === "csv" ? "csv" : "xlsx";
      link.download = match ? match[1] : `${reportType}-report.${ext}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="flex items-center gap-2 print:hidden">
      <button className="btn-secondary !px-3 !py-1.5 text-xs" onClick={() => download("pdf")} disabled={downloading !== null}>
        {downloading === "pdf" ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />} PDF
      </button>
      <button className="btn-secondary !px-3 !py-1.5 text-xs" onClick={() => download("excel")} disabled={downloading !== null}>
        {downloading === "excel" ? <Loader2 size={13} className="animate-spin" /> : <FileSpreadsheet size={13} />} Excel
      </button>
      <button className="btn-secondary !px-3 !py-1.5 text-xs" onClick={() => download("csv")} disabled={downloading !== null}>
        {downloading === "csv" ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />} CSV
      </button>
      <button className="btn-secondary !px-3 !py-1.5 text-xs" onClick={() => window.print()}>
        <Printer size={13} /> {t("actions.print", "Print")}
      </button>
    </div>
  );
}
