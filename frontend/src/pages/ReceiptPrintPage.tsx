import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import apiClient from "@/api/client";
import { Loader2 } from "lucide-react";

interface ReceiptPrintData {
  receipt_id: number;
  receipt_number: string;
  transaction_number: string;
  transaction_type: string;
  issue_date: string;
  party_label_en: string;
  party_label_ar: string;
  party_name: string | null;
  direction_label_en: string;
  direction_label_ar: string;
  property_title: string | null;
  unit_number: string | null;
  amount: string;
  currency_code: string | null;
  amount_in_words_en: string;
  amount_in_words_ar: string;
  payment_method: string | null;
  reference_number: string | null;
  account_name: string | null;
  description: string | null;
}

/**
 * Generic printable receipt for tenant_payment AND owner_payment
 * transactions — the counterpart to RentVoucherPrintPage for
 * everything that isn't specifically a tenant's monthly rent. Raised
 * directly: paying an owner had no printable, signable document at
 * all before this. Deliberately simpler than the Rent Voucher (one
 * receipt, not a tenant/company pair, no QR) — that level of format
 * was requested specifically for rent collection, not for this.
 */
export default function ReceiptPrintPage() {
  const { receiptId } = useParams<{ receiptId: string }>();
  const [data, setData] = useState<ReceiptPrintData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!receiptId) return;
    apiClient.get<ReceiptPrintData>(`/financial/receipts/${receiptId}/print-data`)
      .then(({ data }) => {
        setData(data);
        // Fire-and-forget print-count tracking, same as the Rent
        // Voucher module — never blocks the page from rendering.
        apiClient.post(`/financial/receipts/${receiptId}/print`).catch(() => {});
      })
      .catch((err) => setError(err?.response?.data?.detail || "Could not load this receipt."))
      .finally(() => setLoading(false));
  }, [receiptId]);

  if (loading) return <div className="flex justify-center p-10"><Loader2 className="animate-spin" /></div>;
  if (error || !data) return <div className="p-10 text-center text-rust-500">{error || "Receipt not found."}</div>;

  const amountFormatted = Number(data.amount).toLocaleString(undefined, { minimumFractionDigits: 3 });
  const isOwnerPayment = data.transaction_type === "owner_payment";

  return (
    <div style={{ background: "#e5e5e5", minHeight: "100vh", padding: "10mm 0" }}>
      <style>{`@media print { body { background: #fff !important; } .no-print { display: none !important; } }`}</style>
      <button className="no-print btn-primary" style={{ display: "block", margin: "0 auto 10mm" }} onClick={() => window.print()}>Print</button>

      <div style={{
        width: "190mm", margin: "0 auto", background: "#fff", padding: "10mm 14mm", boxShadow: "0 4px 18px rgba(0,0,0,0.15)",
        fontFamily: "Arial, Helvetica, sans-serif", fontSize: "13px", color: "#000",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "2px solid #000", paddingBottom: "6px", marginBottom: "10px" }}>
          <div style={{ fontWeight: 900, fontSize: "24px" }}>PAYMENT RECEIPT</div>
          <div dir="rtl" style={{ fontWeight: 900, fontSize: "24px" }}>إيصال دفع</div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #ccc", marginBottom: "10px" }}>
          <div><strong>Receipt No.</strong> · <span dir="rtl">رقم الإيصال</span><br />{data.receipt_number}</div>
          <div style={{ textAlign: "right" }}><strong>Date</strong> · <span dir="rtl">التاريخ</span><br />{data.issue_date}</div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "14px" }}>
          <tbody>
            <tr>
              <td style={{ border: "1px solid #999", padding: "6px 9px", fontWeight: 700, width: "35%" }}>
                {data.direction_label_en} · <span dir="rtl">{data.direction_label_ar}</span>
              </td>
              <td style={{ border: "1px solid #999", padding: "6px 9px" }}>{data.party_name || "—"}</td>
            </tr>
            {(data.property_title || data.unit_number) && (
              <tr>
                <td style={{ border: "1px solid #999", padding: "6px 9px", fontWeight: 700 }}>Property · <span dir="rtl">العقار</span></td>
                <td style={{ border: "1px solid #999", padding: "6px 9px" }}>{[data.property_title, data.unit_number].filter(Boolean).join(" — ") || "—"}</td>
              </tr>
            )}
            <tr>
              <td style={{ border: "1px solid #999", padding: "6px 9px", fontWeight: 700 }}>Account · <span dir="rtl">الحساب</span></td>
              <td style={{ border: "1px solid #999", padding: "6px 9px" }}>{data.account_name || "—"}</td>
            </tr>
            <tr>
              <td style={{ border: "1px solid #999", padding: "6px 9px", fontWeight: 700 }}>Payment Method · <span dir="rtl">طريقة الدفع</span></td>
              <td style={{ border: "1px solid #999", padding: "6px 9px" }}>{data.payment_method || "—"}</td>
            </tr>
            {data.reference_number && (
              <tr>
                <td style={{ border: "1px solid #999", padding: "6px 9px", fontWeight: 700 }}>Reference · <span dir="rtl">المرجع</span></td>
                <td style={{ border: "1px solid #999", padding: "6px 9px" }}>{data.reference_number}</td>
              </tr>
            )}
          </tbody>
        </table>

        <div style={{ border: "1.5px solid #000", borderRadius: "3px", padding: "8px 12px", marginBottom: "18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><strong>Amount</strong> · <span dir="rtl">المبلغ</span><div style={{ fontSize: "20px", fontWeight: 900 }}>{amountFormatted} {data.currency_code || ""}</div></div>
          <div style={{ textAlign: "right", maxWidth: "60%" }}>
            <div>{data.amount_in_words_en}</div>
            <div dir="rtl">{data.amount_in_words_ar}</div>
          </div>
        </div>

        {data.description && <p style={{ fontSize: "12px", color: "#555", marginBottom: "18px" }}>{data.description}</p>}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", textAlign: "center", marginTop: "30px" }}>
          <div>
            <div style={{ borderBottom: "1.5px solid #666", height: "2em" }} />
            <div style={{ marginTop: "4px", fontWeight: 700 }}>Prepared By · <span dir="rtl">أعده</span></div>
          </div>
          <div>
            <div style={{ borderBottom: "1.5px solid #666", height: "2em" }} />
            <div style={{ marginTop: "4px", fontWeight: 700 }}>
              {isOwnerPayment ? "Owner Signature · " : "Received By · "}
              <span dir="rtl">{isOwnerPayment ? "توقيع المالك" : "استلم بواسطة"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
