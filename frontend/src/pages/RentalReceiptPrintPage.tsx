import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { RentalReceipt } from "@/types";
import { Loader2, Printer, ArrowLeft } from "lucide-react";

// Physical page sizes (landscape), per the approved Rental Receipt design
// (Concept B — Mirror Split, approved 2026-07-19):
//   - "half" is the default: Half A4 Landscape, 297mm x 105mm — NOT the
//     ISO half-cut of A4 (that's A5, 210x148mm). This is two receipts
//     stacked on one A4 landscape sheet, for pre-cut/perforated
//     letterhead stock, per spec.
//   - "full" (plain A4 landscape) is kept as a fallback for printers
//     without pre-cut paper — pre-existing option, unrelated to the
//     approved design, unaffected by it.
//   - Quarter A4 was scoped out of this phase (see approval). The
//     natural companion cut once it's needed is 148.5mm x 105mm
//     (halving the width again, keeping the same 105mm height) — adding
//     it back is just one more PAGE_SIZES entry plus width-based
//     responsive tweaks in the two `.half` columns below, nothing in
//     this file's structure needs to change.
const PAGE_SIZES: Record<string, { width: string; height: string }> = {
  full: { width: "297mm", height: "210mm" },
  half: { width: "297mm", height: "105mm" },
};

const PAYMENT_METHOD_LABELS: Record<string, { en: string; ar: string }> = {
  cash: { en: "Cash", ar: "نقدًا" },
  bank_transfer: { en: "Bank Transfer", ar: "تحويل بنكي" },
  cheque: { en: "Cheque", ar: "شيك" },
};

export default function RentalReceiptPrintPage() {
  const { installmentId } = useParams<{ installmentId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const copy = (searchParams.get("copy") === "company" ? "company" : "tenant") as "tenant" | "company";
  const size = PAGE_SIZES[searchParams.get("size") || "half"] ? (searchParams.get("size") || "half") : "half";

  const [receipt, setReceipt] = useState<RentalReceipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [printing, setPrinting] = useState(false);

  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setLoadError(null);
    apiClient.get<RentalReceipt>(`/rentals/installments/${installmentId}/receipt`)
      .then(({ data }) => setReceipt(data))
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        const status = err?.response?.status;
        const code = err?.code ? ` [${err.code}]` : "";
        setLoadError(detail || (status ? `Request failed with status ${status}` : `Network error — could not reach the server${code}`));
      })
      .finally(() => setLoading(false));
  }, [installmentId]);

  useEffect(() => { load(); }, [load]);

  const handlePrint = async () => {
    setPrinting(true);
    try {
      // Records the print/reprint for the audit trail (see Phase 1 §15)
      // before the browser's print dialog opens — the receipt content
      // itself never changes as a result of this call.
      const { data } = await apiClient.post<RentalReceipt>(`/rentals/installments/${installmentId}/receipt/print`);
      setReceipt(data);
      setTimeout(() => window.print(), 100);
    } finally {
      setPrinting(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center items-center h-screen"><Loader2 className="animate-spin text-ink-400" size={28} /></div>;
  }
  if (!receipt) {
    return <div className="flex flex-col items-center justify-center h-screen gap-3 text-ink-500 px-6 text-center">
      <p>This receipt could not be loaded.</p>
      {loadError && <p className="text-sm text-rust-500 max-w-md">{loadError}</p>}
      <div className="flex gap-2">
        <button className="btn-secondary" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Back</button>
        <button className="btn-secondary" onClick={load}>Retry</button>
      </div>
    </div>;
  }

  const amountFormatted = Number(receipt.amount).toLocaleString(undefined, { minimumFractionDigits: 3 });
  const buildingLine = [receipt.building_name, receipt.building_number].filter(Boolean).join(" / ") || "—";
  const unitLine = [receipt.unit_name, receipt.unit_number].filter(Boolean).join(" / ") || "—";
  const paymentLabel = receipt.payment_method ? (PAYMENT_METHOD_LABELS[receipt.payment_method] || { en: receipt.payment_method, ar: receipt.payment_method }) : null;

  return (
    <div className="bg-ink-200 min-h-screen py-6 print:bg-white print:py-0">
      <style>{`
        @page { size: ${PAGE_SIZES[size].width} ${PAGE_SIZES[size].height}; margin: 0; }
        @media print {
          html, body { background: white !important; }
          .receipt-toolbar { display: none !important; }
          .receipt-sheet { box-shadow: none !important; margin: 0 !important; }
        }
      `}</style>

      <div className="receipt-toolbar max-w-4xl mx-auto mb-4 flex items-center justify-between px-4">
        <button className="btn-secondary" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Back</button>
        <div className="flex items-center gap-2">
          <span className="text-sm text-ink-600 bg-white px-3 py-1.5 rounded-md border border-ink-200 capitalize">{copy} copy · {size === "half" ? "Half A4 landscape (297×105mm)" : "Full A4 landscape"}</span>
          <button className="btn-primary" onClick={handlePrint} disabled={printing}>
            {printing ? <Loader2 size={16} className="animate-spin" /> : <Printer size={16} />} Print
          </button>
        </div>
      </div>

      {/* The printable sheet itself — Concept B (Mirror Split), approved
          2026-07-19. Letterhead-safe: no logo, no company header/address
          block. Two independent, mirrored halves rather than dual-
          language labels on each line, so a single-language reader never
          has to parse a mixed-language line. Intentionally plain inline
          styling rather than the app's Tailwind component classes, since
          this must render identically and predictably in print
          regardless of the app's theme (including dark mode, which must
          never bleed into a printed page). Never shows payment_status —
          the printed receipt is final for the tenant. */}
      <div
        className="receipt-sheet bg-white mx-auto shadow-floating relative"
        style={{ width: PAGE_SIZES[size].width, height: PAGE_SIZES[size].height, display: "flex", fontSize: "9px" }}
        dir="ltr"
      >
        {copy === "company" && (
          <div style={{ position: "absolute", top: "3mm", left: "50%", transform: "translateX(-50%)", fontSize: "8px", color: "#999", letterSpacing: "1px", textTransform: "uppercase" }}>
            Company Copy · نسخة الشركة
          </div>
        )}

        {/* Arabic half — right-to-left, mirrors the English half exactly */}
        <ReceiptHalf
          dir="rtl"
          title="إيصال إيجار"
          metaLabel="رقم الإيصال"
          metaValue={receipt.receipt_number}
          dateLabel="التاريخ"
          dateValue={receipt.receipt_date}
          rows={[
            ["المستأجر", receipt.tenant_name],
            ["العنوان", receipt.tenant_address || "—"],
            ["شهر الإيجار", receipt.rental_month],
            ["المبنى", buildingLine],
            ["الوحدة", unitLine],
            ["المبلغ", amountFormatted],
          ]}
          wordsLabel="المبلغ كتابةً"
          wordsValue={receipt.amount_in_words_ar}
          paymentLabel="طريقة الدفع"
          paymentValue={paymentLabel?.ar}
          bankLabel="اسم البنك"
          bankValue={receipt.bank_name}
          refLabel={receipt.payment_method === "cheque" ? "رقم الشيك" : "الرقم المرجعي"}
          refValue={receipt.reference_number}
          sig1="توقيع المستأجر"
          sig2="توقيع الموظف"
          sig3="ختم الشركة"
        />

        <div style={{ width: "1px", background: "#B8BDB9", margin: "5mm 0" }} />

        {/* English half — left-to-right */}
        <ReceiptHalf
          dir="ltr"
          title="Rental Receipt"
          metaLabel="Receipt No."
          metaValue={receipt.receipt_number}
          dateLabel="Date"
          dateValue={receipt.receipt_date}
          rows={[
            ["Tenant", receipt.tenant_name],
            ["Address", receipt.tenant_address || "—"],
            ["Rental Month", receipt.rental_month],
            ["Building", buildingLine],
            ["Unit", unitLine],
            ["Amount", amountFormatted],
          ]}
          wordsLabel="Amount in words"
          wordsValue={receipt.amount_in_words_en}
          paymentLabel="Payment Method"
          paymentValue={paymentLabel?.en}
          bankLabel="Bank Name"
          bankValue={receipt.bank_name}
          refLabel={receipt.payment_method === "cheque" ? "Cheque Number" : "Reference Number"}
          refValue={receipt.reference_number}
          sig1="Tenant Signature"
          sig2="Employee Signature"
          sig3="Company Stamp"
        />
      </div>
    </div>
  );
}

function ReceiptHalf({
  dir, title, metaLabel, metaValue, dateLabel, dateValue, rows,
  wordsLabel, wordsValue, paymentLabel, paymentValue, bankLabel, bankValue, refLabel, refValue,
  sig1, sig2, sig3,
}: {
  dir: "ltr" | "rtl";
  title: string; metaLabel: string; metaValue: string; dateLabel: string; dateValue: string;
  rows: [string, string][];
  wordsLabel: string; wordsValue: string;
  paymentLabel: string; paymentValue?: string;
  bankLabel: string; bankValue?: string | null;
  refLabel: string; refValue?: string | null;
  sig1: string; sig2: string; sig3: string;
}) {
  return (
    <div dir={dir} style={{ flex: 1, padding: "6mm 8mm 4mm", display: "flex", flexDirection: "column", minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1.5px solid #171D19", paddingBottom: "4px", marginBottom: "6px" }}>
        <span style={{ fontWeight: 700, fontSize: "13px" }}>{title}</span>
        <span style={{ fontSize: "9px", textAlign: "end" }}>
          {metaLabel}: <strong>{metaValue}</strong> · {dateLabel}: <strong>{dateValue}</strong>
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px dotted #ccc", paddingBottom: "2px" }}>
            <span style={{ color: "#666" }}>{label}</span>
            <span style={{ fontWeight: 600 }}>{value}</span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: "6px", padding: "5px 8px", border: "1px solid #ccc", borderRadius: "4px", fontSize: "8.5px", lineHeight: 1.45 }}>
        {wordsLabel}: <strong>{wordsValue}</strong>
      </div>

      {/* Payment section — only rendered once payment is confirmed
          (payment_method comes back null on a receipt printed before
          payment, which is this system's normal workflow). No "Paid" /
          "Pending" / status word anywhere, per spec — showing HOW it was
          paid is fine, showing status is not. */}
      {paymentValue && (
        <div style={{ marginTop: "5px", fontSize: "8.5px", display: "flex", flexDirection: "column", gap: "2px" }}>
          <div>{paymentLabel}: <strong>{paymentValue}</strong></div>
          {bankValue && <div>{bankLabel}: <strong>{bankValue}</strong></div>}
          {refValue && <div>{refLabel}: <strong>{refValue}</strong></div>}
        </div>
      )}

      <div style={{ marginTop: "auto", paddingTop: "8px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", fontSize: "8px", textAlign: "center" }}>
        <SignatureBox label={sig1} />
        <SignatureBox label={sig2} />
        <SignatureBox label={sig3} />
      </div>
    </div>
  );
}

function SignatureBox({ label }: { label: string }) {
  return (
    <div>
      <div style={{ borderBottom: "1px solid #999", height: "18px" }} />
      <div style={{ marginTop: "3px", color: "#666" }}>{label}</div>
    </div>
  );
}
