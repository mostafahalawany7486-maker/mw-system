"""
QR code generation for printable invoices/receipts. Self-contained
utility (mirrors app/core/number_to_words.py's pattern) — nothing like
this existed anywhere in the codebase before the Rent Billing Engine.

Per spec: the QR code must contain only the invoice ID, invoice number,
and a verification URL — "nothing sensitive". It never encodes amounts,
tenant details, or payment information.
"""
import base64
from io import BytesIO

import qrcode


def generate_invoice_qr_data_uri(verification_url: str) -> str:
    """Returns a `data:image/png;base64,...` URI ready to drop straight
    into an <img src="..."> in the browser-print template, or to decode
    back to bytes for embedding in a generated PDF (see
    report_export_service.py's pattern for the latter)."""
    img = qrcode.make(verification_url, box_size=6, border=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_invoice_qr_png_bytes(verification_url: str) -> bytes:
    """Raw PNG bytes — for embedding in a server-generated PDF rather
    than a browser-rendered data URI."""
    img = qrcode.make(verification_url, box_size=6, border=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
