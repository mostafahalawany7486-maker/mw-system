import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { InvoicePrintData } from "@/types";
import { Loader2, Printer, ArrowLeft } from "lucide-react";

const PAGE_SIZES: Record<string, { width: string; height: string }> = {
  full: { width: "297mm", height: "210mm" },
  half: { width: "210mm", height: "148mm" },
  quarter: { width: "148mm", height: "105mm" },
};

export default function InvoicePrintPage() {
  const { invoiceId } = useParams<{ invoiceId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const copy = (searchParams.get("copy") === "company" ? "company" : "tenant") as "tenant" | "company";
  const size = PAGE_SIZES[searchParams.get("size") || "half"] ? (searchParams.get("size") || "half") : "half";

  const [invoice, setInvoice] = useState<InvoicePrintData | null>(null);
  const [loading, setLoading] = useState(true);
  const [printing, setPrinting] = useState(false);

  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setLoadError(null);
    apiClient.get<InvoicePrintData>(`/financial/invoices/${invoiceId}/print-data`)
      .then(({ data }) => setInvoice(data))
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        const status = err?.response?.status;
        const code = err?.code ? ` [${err.code}]` : "";
        setLoadError(detail || (status ? `Request failed with status ${status}` : `Network error — could not reach the server${code}`));
      })
      .finally(() => setLoading(false));
  }, [invoiceId]);

  useEffect(() => { load(); }, [load]);

  const handlePrint = async () => {
    setPrinting(true);
    try {
      const { data } = await apiClient.post<InvoicePrintData>(`/financial/invoices/${invoiceId}/print`);
      setInvoice(data);
      setTimeout(() => window.print(), 100);
    } finally {
      setPrinting(false);
    }
  };

  if (loading) return <div className="flex justify-center items-center h-screen"><Loader2 className="animate-spin text-ink-400" size={28} /></div>;
  if (!invoice) return <div className="flex flex-col items-center justify-center h-screen gap-3 text-ink-500 px-6 text-center">
    <p>This invoice could not be loaded.</p>
    {loadError && <p className="text-sm text-rust-500 max-w-md">{loadError}</p>}
    <div className="flex gap-2">
      <button className="btn-secondary" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Back</button>
      <button className="btn-secondary" onClick={load}>Retry</button>
    </div>
  </div>;

  const discountLine = invoice.discount_value && Number(invoice.discount_value) > 0
    ? `${invoice.discount_value}${invoice.discount_type === "percentage" ? "%" : ""}` : "—";

  return (
    <div className="bg-ink-200 min-h-screen py-6 print:bg-white print:py-0">
      <style>{`
        @page { size: ${PAGE_SIZES[size].width} ${PAGE_SIZES[size].height}; margin: 0; }
        @media print {
          html, body { background: white !important; }
          .invoice-toolbar { display: none !important; }
          .invoice-sheet { box-shadow: none !important; margin: 0 !important; }
        }
      `}</style>

      <div className="invoice-toolbar max-w-4xl mx-auto mb-4 flex items-center justify-between px-4">
        <button className="btn-secondary" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Back</button>
        <div className="flex items-center gap-2">
          <span className="text-sm text-ink-600 bg-white px-3 py-1.5 rounded-md border border-ink-200 capitalize">{copy} copy · {size} A4 landscape</span>
          <button className="btn-primary" onClick={handlePrint} disabled={printing}>
            {printing ? <Loader2 size={16} className="animate-spin" /> : <Printer size={16} />} Print
          </button>
        </div>
      </div>

      {/* Letterhead-safe: no logo/header block printed — the pre-printed
          paper already has it. Plain inline styling (not Tailwind
          component classes) so this renders identically regardless of
          the app's theme, same reasoning as RentalReceiptPrintPage. */}
      <div
        className="invoice-sheet bg-white mx-auto shadow-floating relative"
        style={{ width: PAGE_SIZES[size].width, minHeight: PAGE_SIZES[size].height, padding: "12mm 12mm 8mm" }}
        dir="ltr"
      >
        {copy === "company" && (
          <div style={{ position: "absolute", top: "6mm", right: "10mm", fontSize: "9px", color: "#999", letterSpacing: "1px", textTransform: "uppercase" }}>
            Company Copy
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "2px solid #171D19", paddingBottom: "6px", marginBottom: "8px" }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: "15px" }}>RENT INVOICE</div>
            <div style={{ fontSize: "10px", color: "#666", marginTop: "2px" }}>{invoice.company_name}</div>
            {invoice.company_address && <div style={{ fontSize: "9px", color: "#888" }}>{invoice.company_address}</div>}
          </div>
          <div style={{ textAlign: "right", fontSize: "10.5px" }}>
            <div>Invoice No.: <strong>{invoice.invoice_number}</strong></div>
            <div>Issue Date: <strong>{invoice.issue_date}</strong></div>
            <div>Due Date: <strong>{invoice.due_date}</strong></div>
          </div>
          {invoice.qr_code_data_uri && (
            <img src={invoice.qr_code_data_uri} alt="Verification QR code" style={{ width: "22mm", height: "22mm" }} />
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px", fontSize: "10.5px", marginBottom: "8px" }}>
          <div>
            <div style={{ fontWeight: 600, color: "#666", fontSize: "9px", textTransform: "uppercase", marginBottom: "3px" }}>Tenant</div>
            <div>{invoice.tenant_name}</div>
            {invoice.tenant_address && <div style={{ color: "#666" }}>{invoice.tenant_address}</div>}
            {copy === "company" && invoice.tenant_civil_id && <div style={{ color: "#666" }}>Civil ID: {invoice.tenant_civil_id}</div>}
            {copy === "company" && invoice.tenant_phone && <div style={{ color: "#666" }}>{invoice.tenant_phone}</div>}
          </div>
          <div>
            <div style={{ fontWeight: 600, color: "#666", fontSize: "9px", textTransform: "uppercase", marginBottom: "3px" }}>Property</div>
            <div>{[invoice.building_name, invoice.unit_number].filter(Boolean).join(" — ") || invoice.property_title}</div>
            {copy === "company" && invoice.contract_number && <div style={{ color: "#666" }}>Contract: {invoice.contract_number}</div>}
            {invoice.billing_period_start && <div style={{ color: "#666" }}>{invoice.billing_period_start} to {invoice.billing_period_end}</div>}
          </div>
        </div>

        <table style={{ width: "100%", fontSize: "10.5px", borderCollapse: "collapse", marginBottom: "8px" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #ccc", borderTop: "1px solid #ccc" }}>
              <th style={{ textAlign: "left", padding: "4px 0" }}>Description</th>
              <th style={{ textAlign: "right", padding: "4px 0" }}>Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr><td style={{ padding: "3px 0" }}>Rent</td><td style={{ textAlign: "right" }}>{invoice.rent_amount ?? "—"}</td></tr>
            <tr><td style={{ padding: "3px 0" }}>Discount</td><td style={{ textAlign: "right" }}>{discountLine}</td></tr>
            <tr><td style={{ padding: "3px 0" }}>VAT</td><td style={{ textAlign: "right" }}>{invoice.tax_rate ? `${invoice.tax_rate}%` : "—"}</td></tr>
            <tr style={{ borderTop: "1px solid #ccc", fontWeight: 700 }}>
              <td style={{ padding: "4px 0" }}>Total</td><td style={{ textAlign: "right" }}>{Number(invoice.amount).toLocaleString(undefined, { minimumFractionDigits: 3 })}</td>
            </tr>
            <tr>
              <td style={{ padding: "3px 0", color: "#666" }}>Outstanding Balance</td>
              <td style={{ textAlign: "right", color: "#666" }}>{Number(invoice.outstanding_amount).toLocaleString(undefined, { minimumFractionDigits: 3 })}</td>
            </tr>
          </tbody>
        </table>

        {copy === "company" && (
          <div style={{ marginTop: "10px", paddingTop: "10px", borderTop: "1px dashed #ccc", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px", fontSize: "10px" }}>
            <div><div style={{ borderBottom: "1px solid #999", height: "24px" }} /><div style={{ marginTop: "4px", color: "#666" }}>Collector</div></div>
            <div><div style={{ borderBottom: "1px solid #999", height: "24px" }} /><div style={{ marginTop: "4px", color: "#666" }}>Payment Method</div></div>
            <div><div style={{ borderBottom: "1px solid #999", height: "24px" }} /><div style={{ marginTop: "4px", color: "#666" }}>Transaction No.</div></div>
          </div>
        )}

        <div style={{ position: "absolute", bottom: "8mm", left: "12mm", right: "12mm", fontSize: "8.5px", color: "#999", borderTop: "1px solid #eee", paddingTop: "4px" }}>
          Accepted: Cash, Bank Transfer, Cheque, K-NET · Please settle by the due date shown above. Thank you.
        </div>
      </div>
    </div>
  );
}
