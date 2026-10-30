import { useEffect, useState, useCallback, useRef, Fragment } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { RentVoucherPrintData } from "@/types";
import { Loader2, Printer, ArrowLeft } from "lucide-react";

// Per spec's PAYMENT METHOD section — the checkbox that matches the
// voucher's actual payment_method (set automatically from the
// underlying payment transaction, per spec) is filled; the rest stay
// empty boxes. "other" is the fallback the backend already uses for
// any method not in this list (see PAYMENT_METHOD_LABELS,
// app/models/rent_voucher.py).
const PAYMENT_METHODS: { value: string; en: string; ar: string }[] = [
  { value: "cash", en: "Cash", ar: "نقدي" },
  { value: "bank_transfer", en: "Bank Transfer", ar: "تحويل بنكي" },
  { value: "cheque", en: "Cheque", ar: "شيك" },
  { value: "knet", en: "K-Net", ar: "كي نت" },
  { value: "other", en: "Other", ar: "أخرى" },
];

// A4 portrait. Per spec: "Leave enough blank space at the top and
// bottom of each voucher area. The voucher must print correctly
// without overlapping the letterhead." Two vouchers per page (one
// tenant's pair), each preceded by its own reserved blank band for
// the physical letterhead — see the page-structure comment below for
// the exact layout and defaults.
// Page structure, per request: a reserved white band for the company
// logo/stamp BEFORE each of the 2 vouchers (not just between them) —
// [15% white][tenant copy][15% white][company copy][small bottom
// margin]. Both the "before voucher 1" and "before voucher 2" bands
// default to the same 15%-of-A4-height size but are independently
// overridable via ?marginTop=/?gap= (mm), and the trailing bottom
// margin via ?marginBottom=.
const PAGE_WIDTH = "210mm";
const PAGE_HEIGHT = "297mm";
const DEFAULT_MARGIN_TOP_MM = 41.5; // ~14% of 297mm (was 15%) — 1% given back to the voucher content, per request, so Payment Method never risks clipping
const DEFAULT_MARGIN_BOTTOM_MM = 8;
// White band before the company's copy (i.e. between the two
// vouchers) — also ~15% of the A4 page height, per request.
const DEFAULT_GAP_MM = 41.5; // ~14% of 297mm (was 15%) — same 1% given back, per request
const DEFAULT_BASE_FONT_PX = 9.5; // reduced again from 10.5 — requested directly a second time, so recent additions (Month label, floor unit numbers list) don't push the bottom of the voucher past the printable area

// No QR-rendering library is a project dependency (see
// docs/rent-voucher-module.md's "BARCODE REQUIREMENT" section for the
// same reasoning, now applied to QR — avoiding a new backend
// dependency for something the browser can render just as well).
// qrcodejs is loaded from a CDN at runtime, once, and reused for every
// voucher on the page.
let qrCodeLoadPromise: Promise<void> | null = null;
function loadQRCodeLib(): Promise<void> {
  if ((window as any).QRCode) return Promise.resolve();
  if (qrCodeLoadPromise) return qrCodeLoadPromise;
  qrCodeLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("QR code library failed to load"));
    document.head.appendChild(script);
  });
  return qrCodeLoadPromise;
}

function VoucherQRCode({ value }: { value: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadQRCodeLib().then(() => { if (!cancelled) setReady(true); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (ready && ref.current && (window as any).QRCode) {
      ref.current.innerHTML = ""; // clear on re-render (e.g. value change) — the library appends, it doesn't replace
      // eslint-disable-next-line no-new
      new (window as any).QRCode(ref.current, { text: value, width: 52, height: 52, correctLevel: 1 });
    }
  }, [ready, value]);

  // Renders empty (no visible gap beyond the reserved slot) until the
  // library loads — never blocks the rest of the voucher from showing.
  return <div ref={ref} style={{ display: "inline-block" }} />;
}

export default function RentVoucherPrintPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const idsParam = searchParams.get("ids") || "";
  const ids = idsParam.split(",").map((s) => parseInt(s, 10)).filter((n) => !isNaN(n));
  const marginTop = Number(searchParams.get("marginTop")) || DEFAULT_MARGIN_TOP_MM;
  const marginBottom = Number(searchParams.get("marginBottom")) || DEFAULT_MARGIN_BOTTOM_MM;
  const gapMm = searchParams.get("gap") !== null ? Number(searchParams.get("gap")) : DEFAULT_GAP_MM;
  const baseFontPx = Number(searchParams.get("fontSize")) || DEFAULT_BASE_FONT_PX;
  // 2 vouchers per A4 sheet (one tenant's pair: their copy + the
  // company's copy) — one gap between them, reserved for the company
  // logo/name, pre-printed on letterhead stock rather than rendered here.
  const voucherHeightMm = (297 - marginTop - marginBottom - gapMm) / 2;
  // Optional watermark support, per spec's DESIGN REQUIREMENTS — off by
  // default, opt in via ?watermark=SAMPLE (or DUPLICATE, VOID, etc.).
  const watermarkText = searchParams.get("watermark") || undefined;
  // "?source=pending" reuses this exact same rendering for Pending Rent
  // Slips (printed before collection — see PendingRentSlipService) —
  // identical shape/dimensions/content, per request. The only
  // difference is which endpoints supply/track the data; VoucherSlot
  // itself needs no changes since both DTOs share the same field shape.
  const source = searchParams.get("source") === "pending" ? "pending" : "voucher";
  const printDataUrl = source === "pending" ? "/pending-rent-slips/print-data/bulk" : "/rent-vouchers/print-data/bulk";
  const idsBodyKey = source === "pending" ? "slip_ids" : "voucher_ids";
  const recordPrintUrl = (id: number) => source === "pending" ? `/pending-rent-slips/${id}/record-print` : `/rent-vouchers/${id}/record-print`;

  const [vouchers, setVouchers] = useState<RentVoucherPrintData[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [printing, setPrinting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (ids.length === 0) {
      setLoadError("No voucher IDs were given — open this page as /rent-vouchers/print?ids=12,13,14,15 (any number — 2 per A4 sheet, one page per tenant).");
      setLoading(false);
      setVouchers(null);
      return;
    }
    setLoading(true);
    setLoadError(null);
    apiClient.post<RentVoucherPrintData[]>(printDataUrl, { [idsBodyKey]: ids })
      .then(({ data }) => setVouchers(data))
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        const status = err?.response?.status;
        const code = err?.code ? ` [${err.code}]` : "";
        setLoadError(detail || (status ? `Request failed with status ${status}` : `Network error — could not reach the server${code}`));
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsParam]);

  useEffect(() => { load(); }, [load]);

  const handlePrint = async () => {
    if (!vouchers || vouchers.length === 0) return;
    setPrinting(true);
    try {
      // Records the print/reprint for each voucher's own audit trail
      // (print_count / printed_at) before the browser's print dialog
      // opens — same sequencing as RentalReceiptPrintPage / InvoicePrintPage.
      await Promise.all(vouchers.map((v) => apiClient.post(recordPrintUrl(v.voucher_id))));
      setTimeout(() => window.print(), 100);
    } finally {
      setPrinting(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center items-center h-screen"><Loader2 className="animate-spin text-ink-400" size={28} /></div>;
  }
  if (!vouchers || vouchers.length === 0) {
    return <div className="flex flex-col items-center justify-center h-screen gap-3 text-ink-500 px-6 text-center">
      <p>These vouchers could not be loaded.</p>
      {loadError && <p className="text-sm text-rust-500 max-w-md">{loadError}</p>}
      <div className="flex gap-2">
        <button className="btn-secondary" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Back</button>
        <button className="btn-secondary" onClick={load}>Retry</button>
      </div>
    </div>;
  }

  // 2 vouchers (one tenant's pair) per A4 sheet — as many sheets as
  // needed, one after another, each a full physical page (page-break-
  // after between them for print/PDF export). Replaces the old fixed
  // "always exactly 4 slots on one page" layout.
  const pages: (RentVoucherPrintData | null)[][] = [];
  for (let i = 0; i < vouchers.length; i += 2) {
    pages.push([vouchers[i] || null, vouchers[i + 1] || null]);
  }

  return (
    <div className="bg-ink-200 min-h-screen py-6 print:bg-white print:py-0">
      <style>{`
        @page { size: A4 portrait; margin: 0; }
        @media print {
          html, body { background: white !important; }
          .voucher-toolbar { display: none !important; }
          .voucher-sheet { box-shadow: none !important; margin: 0 !important; }
          .voucher-margin-guide { border-color: transparent !important; }
          .voucher-gap-label { display: none !important; }
        }
      `}</style>

      <div className="voucher-toolbar max-w-4xl mx-auto mb-4 flex flex-col gap-2 px-4">
        <div className="flex items-center justify-between">
          <button className="btn-secondary" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Back</button>
          <div className="flex items-center gap-2">
            <span className="text-sm text-ink-600 bg-white px-3 py-1.5 rounded-md border border-ink-200">
              {vouchers.length} voucher(s) · {pages.length} A4 page(s) (2 per page) · {marginTop}mm/{marginBottom}mm letterhead margin · {gapMm}mm gap between copies · {baseFontPx}px text
            </span>
            <button className="btn-primary" onClick={handlePrint} disabled={printing}>
              {printing ? <Loader2 size={16} className="animate-spin" /> : <Printer size={16} />} Print / Export PDF
            </button>
          </div>
        </div>
        <p className="text-xs text-ink-400 text-right">
          In the print dialog, pick your physical printer to print on letterhead stock, or choose "Save as PDF" as the destination to export a PDF file — same dialog either way.
        </p>
      </div>

      {/* The printable sheet. The dashed zones top/bottom are the blank
          letterhead margin (spec: "leave enough blank space... must
          print correctly without overlapping the letterhead") — shown
          as a faint guide on screen only (see the @media print rule
          above that makes the guide border transparent when actually
          printed, so nothing but blank paper prints there). */}
      {/* One .voucher-sheet per A4 page, 2 vouchers each (page-break-after
          between sheets for print/PDF). The dashed zones top/bottom are
          the blank letterhead margin (spec: "leave enough blank
          space... must print correctly without overlapping the
          letterhead") — shown as a faint guide on screen only (see the
          @media print rule above that makes the guide border
          transparent when actually printed, so nothing but blank paper
          prints there). */}
      {pages.map((pageVouchers, pageIndex) => (
        <div
          key={pageIndex}
          className="voucher-sheet bg-white mx-auto shadow-floating flex flex-col"
          style={{ width: PAGE_WIDTH, height: PAGE_HEIGHT, marginBottom: pageIndex < pages.length - 1 ? "8mm" : 0, pageBreakAfter: pageIndex < pages.length - 1 ? "always" : "auto" }}
          dir="ltr"
        >
          <div className="voucher-margin-guide" style={{ height: `${marginTop}mm`, borderBottom: "1px dashed #ddd", flexShrink: 0 }} />
          {pageVouchers.map((voucher, i) => (
            <Fragment key={i}>
              <div style={{ height: `${voucherHeightMm}mm`, padding: "1.5mm 4mm", flexShrink: 0 }}>
                {voucher ? <VoucherSlot voucher={voucher} watermarkText={watermarkText} baseFontPx={baseFontPx} source={source} /> : <div style={{ height: "100%", border: "1px dashed #ddd", borderRadius: "2px" }} />}
              </div>
              {/* Reserved blank gap between the tenant's copy and the
                  company's copy — for printing the company logo + name
                  on this run (letterhead stock or a rubber stamp), same
                  idea as the top/bottom page margins. Only rendered
                  between the 2 vouchers, not after the last one. */}
              {i < pageVouchers.length - 1 && gapMm > 0 && (
                <div
                  className="voucher-margin-guide"
                  style={{
                    height: `${gapMm}mm`, flexShrink: 0, borderTop: "1px dashed #ddd", borderBottom: "1px dashed #ddd",
                    display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", color: "#bbb", fontSize: "6px",
                  }}
                >
                  <span className="voucher-gap-label">company logo / stamp · شعار واسم الشركة</span>
                </div>
              )}
            </Fragment>
          ))}
          <div className="voucher-margin-guide" style={{ height: `${marginBottom}mm`, borderTop: "1px dashed #ddd", flexShrink: 0, marginTop: "auto" }} />
        </div>
      ))}
    </div>
  );
}

function VoucherSlot({ voucher: v, watermarkText, baseFontPx, source }: { voucher: RentVoucherPrintData; watermarkText?: string; baseFontPx: number; source: "voucher" | "pending" }) {
  const amountFormatted = Number(v.amount).toLocaleString(undefined, { minimumFractionDigits: 3 });
  const matchedMethod = v.payment_method && PAYMENT_METHODS.some((m) => m.value === v.payment_method)
    ? v.payment_method
    : (v.payment_method ? "other" : null);
  // Everything below scales off this one base size (px) instead of a
  // fixed 6.5px, and the title is set well above it separately so it
  // reads as a dominant half-width header, per request ("الكتابة
  // بخط اكبر" / "كلمة ايصال الايجار بنصف الشاشة").
  const titleFontPx = baseFontPx * 1.9;

  return (
    // Professional border around every voucher — per spec ("Have a
    // professional border... suitable for printing and filing").
    <div style={{ height: "100%", border: "1px solid #171D19", borderRadius: "2px", padding: "1.5mm 4mm", display: "flex", flexDirection: "column", fontSize: `${baseFontPx}px`, position: "relative", boxSizing: "border-box", overflow: "hidden", color: "#000000" }}>
      {watermarkText && (
        <div style={{
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "22px", fontWeight: 800, color: "#171D19", opacity: 0.06, transform: "rotate(-28deg)",
          letterSpacing: "3px", pointerEvents: "none", whiteSpace: "nowrap", zIndex: 0,
        }}>
          {watermarkText}
        </div>
      )}
      <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", flex: 1, minHeight: 0, justifyContent: "space-between" }}>
      {/* Header: one single row — English title on the left, the QR
          code centered between the two titles, Arabic title on the
          right — per request ("don't separate them"). Not three
          independently-centered blocks: the two title cells are fixed
          equal-width flex items so the QR in the middle cell lands at
          the true horizontal center of the voucher regardless of how
          long either title renders. */}
      <div style={{ display: "flex", alignItems: "center", borderBottom: "2px solid #000000", paddingBottom: "2px" }}>
        <div style={{ flex: 1, fontWeight: 900, fontSize: `${titleFontPx}px`, lineHeight: 1.15, color: "#000000", textAlign: "left" }}>RENT VOUCHER</div>
        <div style={{ flexShrink: 0, padding: "0 8px" }}>
          {/* QR content only changed — position/size/look untouched.
              Used to hold barcode_value as plain reference text
              (scanning it just showed that text). Now it's a full URL
              back to this exact voucher, so scanning it opens it. */}
          <VoucherQRCode value={`${window.location.origin}/rent-vouchers/print?ids=${v.voucher_id}${source === "pending" ? "&source=pending" : ""}`} />
        </div>
        <div dir="rtl" style={{ flex: 1, fontWeight: 900, fontSize: `${titleFontPx}px`, lineHeight: 1.15, color: "#000000", textAlign: "right" }}>إيصال إيجار</div>
      </div>

      {/* Voucher meta: Number / Issue Date / Rental Month — rental
          month ONLY, no from/to period, per spec. Boxed, like every
          other section below, so the voucher reads as a set of clearly
          filled blocks rather than loose floating lines with dead
          space around them. */}
      <div style={{ display: "flex", gap: "10px", border: "1px solid #999", borderRadius: "3px", padding: "3px 8px" }}>
        <MetaItem label="Voucher Number" labelAr="رقم الإيصال" value={v.voucher_number} />
        <MetaItem label="Issue Date" labelAr="تاريخ الإصدار" value={v.issue_date} />
        <MetaItem label="Month" labelAr="شهر" value={`${v.rental_month_display_en} / ${v.rental_month_display_ar}`} />
      </div>

      {/* Tenant + Property info — Tenant Name, then PACI Number, then
          Mobile Number, then Email, in that order, per request. */}
      <div style={{ display: "flex", gap: "10px" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "2px", border: "1px solid #999", borderRadius: "3px", padding: "4px 9px" }}>
          <Field label="Tenant Name" labelAr="اسم المستأجر" value={v.tenant_name} />
          <Field label="Mobile Number" labelAr="رقم الجوال" value={v.tenant_phone || "—"} />
          <Field label="Email" labelAr="البريد الإلكتروني" value={v.tenant_email || "—"} />
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "2px", border: "1px solid #999", borderRadius: "3px", padding: "4px 9px" }}>
          <Field label="Building Name" labelAr="اسم المبنى" value={v.building_name || "—"} />
          <Field label={v.floor_unit_numbers ? "Unit Numbers" : "Apartment Number"} labelAr={v.floor_unit_numbers ? "أرقام الوحدات" : "رقم الشقة"} value={v.floor_unit_numbers || v.unit_number || "—"} />
          <Field label="PACI Number" labelAr="الرقم الآلي (PACI)" value={v.unit_paci_number || "—"} />
          <Field label="Property Address" labelAr="عنوان العقار" value={v.property_address || "—"} />
        </div>
      </div>

      {/* Amount + amount in words — same "label / تسمية" then value
          pattern as MetaItem above, so this box reads as one
          consistent style with the meta row instead of its own
          separate layout, per request ("مبلغ الايجار هذا ايضا غير
          منظم"). */}
      <div style={{ padding: "4px 9px", border: "1.5px solid #000000", borderRadius: "3px", display: "flex", justifyContent: "space-between", gap: "10px", alignItems: "flex-start" }}>
        <MetaItem label="Rent Amount" labelAr="مبلغ الإيجار" value={`${amountFormatted} ${v.currency_code || ""}`} />
        <div style={{ flex: 1.4 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "4px", justifyContent: "flex-end", whiteSpace: "nowrap" }}>
            <span style={{ color: "#000000", fontWeight: 700 }}>Amount in Words</span>
            <span style={{ color: "#000000", fontWeight: 700 }}>/</span>
            <span dir="rtl" style={{ color: "#000000", fontWeight: 700 }}>المبلغ كتابة</span>
          </div>
          <div style={{ textAlign: "right", marginTop: "1px" }}>
            <div><strong>{v.amount_in_words_en}</strong></div>
            <div dir="rtl"><strong>{v.amount_in_words_ar}</strong></div>
          </div>
        </div>
      </div>

      {/* Payment method checkboxes — this row was clipping off the
          bottom of the voucher before the layout was tightened, per
          request ("show the hidden Payment Method line"); padding
          reduced here and across the other boxed sections above so
          everything reliably fits within one voucher's height. */}
      <div style={{ border: "1px solid #999", borderRadius: "3px", padding: "3px 9px" }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#000000", fontWeight: 800 }}>Payment Method</span>
          <span dir="rtl" style={{ color: "#000000", fontWeight: 800 }}>طريقة الدفع</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", marginTop: "3px" }}>
          {PAYMENT_METHODS.map((m) => (
            <span key={m.value} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{
                display: "inline-block", width: "1.3em", height: "1.3em", border: "1.5px solid #000000", borderRadius: "2px",
                textAlign: "center", lineHeight: "1.3em", fontSize: "1em", fontWeight: 900, flexShrink: 0,
              }}>
                {matchedMethod === m.value ? "✕" : ""}
              </span>
              <span style={{ fontWeight: 700, color: "#000000" }}>{m.en} / {m.ar}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Signature section — "Received By" and "Tenant Signature" only,
          per request (Date removed — it was pushing this section too
          close to the letterhead gap below it and risking overlap). */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", textAlign: "center" }}>
        <SignatureBox label="Received By" labelAr="استلم بواسطة" />
        <SignatureBox label="Tenant Signature" labelAr="توقيع المستأجر" />
      </div>
    </div>
    </div>
  );
}

// Label combines EN + AR on a single line separated by "/" (instead of
// stacking them on two separate lines), with the value directly beneath
// — keeps a field's number/date/amount visually anchored to its own
// label instead of drifting apart, per request ("رقم الايصال وترجمته
// بعيد عن بعض... اكتبه بجوار بعضهم مع وجود سلاش... وبياناتهم تحتهم
// مباشرة").
function MetaItem({ label, labelAr, value, align = "left" }: { label: string; labelAr: string; value: string; align?: "left" | "right" }) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: "4px", justifyContent: align === "right" ? "flex-end" : "flex-start", whiteSpace: "nowrap" }}>
        <span style={{ color: "#000000", fontWeight: 700 }}>{label}</span>
        <span style={{ color: "#000000", fontWeight: 700 }}>/</span>
        <span dir="rtl" style={{ color: "#000000", fontWeight: 700 }}>{labelAr}</span>
      </div>
      <div style={{ fontWeight: 700, color: "#000000", marginTop: "1px", textAlign: align }}>{value}</div>
    </div>
  );
}

// Tenant/property detail rows use a compact "EN · AR" single line
// rather than full two-line stacking (unlike the header and voucher
// meta fields above, which match the spec's own example exactly) —
// a deliberate space trade-off: six of these fields share the block
// between the header and the amount box, and stacking all of them
// would not fit within a quarter-A4 voucher once the letterhead
// margins are reserved. The label text itself is still fully
// bilingual, just laid out horizontally instead of vertically here.
function Field({ label, labelAr, value }: { label: string; labelAr: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "6px", borderBottom: "1px dotted #ddd" }}>
      <span>
        <span style={{ color: "#000000", fontWeight: 700 }}>{label}</span>{" · "}
        <span dir="rtl" style={{ color: "#000000", fontWeight: 700 }}>{labelAr}</span>
      </span>
      <span style={{ fontWeight: 700, whiteSpace: "nowrap", color: "#000000" }}>{value}</span>
    </div>
  );
}


function SignatureBox({ label, labelAr }: { label: string; labelAr: string }) {
  return (
    <div>
      <div style={{ borderBottom: "1.5px solid #666", height: "1.8em" }} />
      <div style={{ marginTop: "3px", color: "#000000", fontWeight: 700 }}>{label}</div>
      <div dir="rtl" style={{ color: "#000000", fontWeight: 700 }}>{labelAr}</div>
    </div>
  );
}
