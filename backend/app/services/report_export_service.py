"""
Enterprise Reporting extension: PDF and Excel export.

Neither capability existed anywhere in this codebase before (confirmed
during the initial audit for this phase — no PDF/Excel library was a
dependency). This module is deliberately generic: it takes an already-
normalized "report document" (a title plus a list of sections, each
either a table or a list of key/value summary rows) and renders it to
bytes. It has no knowledge of what a Property Report or a Maintenance
Report *means* — that logic all stays in ReportsService/
AccountingReportService, which is what "reuse the existing report
engine" means here. Adding an export for a brand-new report type in the
future is just writing one small function that maps that report's dict
into this generic `ReportDocument` shape — never touching this file.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


@dataclass
class ReportTable:
    heading: str
    columns: list[str]
    rows: list[list[Any]]


@dataclass
class ReportSummary:
    heading: str
    items: list[tuple[str, Any]]  # (label, value) pairs


@dataclass
class ReportDocument:
    title: str
    subtitle: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)
    summaries: list[ReportSummary] = field(default_factory=list)
    tables: list[ReportTable] = field(default_factory=list)


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


class ReportPDF(FPDF):
    def __init__(self, doc: ReportDocument):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.doc = doc
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, self.doc.title, ln=1)
        if self.doc.subtitle:
            self.set_font("Helvetica", "", 10)
            self.set_text_color(90, 90, 90)
            self.cell(0, 6, self.doc.subtitle, ln=1)
            self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Generated {self.doc.generated_at.strftime('%Y-%m-%d %H:%M UTC')} — Page {self.page_no()}", align="C")


def render_pdf(doc: ReportDocument) -> bytes:
    pdf = ReportPDF(doc)
    pdf.add_page()

    for summary in doc.summaries:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, summary.heading, ln=1)
        pdf.set_font("Helvetica", "", 9)
        col_width = pdf.w / 4
        x_start = pdf.get_x()
        for i, (label, value) in enumerate(summary.items):
            if i % 4 == 0 and i > 0:
                pdf.ln(6)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(110, 110, 110)
            pdf.cell(col_width, 5, label, border=0)
            pdf.set_xy(pdf.get_x(), pdf.get_y())
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(0, 0, 0)
        x = x_start
        for i, (label, value) in enumerate(summary.items):
            if i % 4 == 0 and i > 0:
                pdf.ln(7)
                x = x_start
            pdf.set_xy(x, pdf.get_y())
            pdf.cell(col_width, 6, _fmt(value), border=0)
            x += col_width
        pdf.ln(10)

    for table in doc.tables:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, table.heading, ln=1)
        if not table.rows:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(140, 140, 140)
            pdf.cell(0, 6, "No data for this section.", ln=1)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4)
            continue

        usable_width = pdf.w - pdf.l_margin - pdf.r_margin
        col_width = usable_width / max(len(table.columns), 1)

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 233, 231)
        for col in table.columns:
            pdf.cell(col_width, 6, col[:28], border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for row in table.rows:
            for cell in row:
                pdf.cell(col_width, 6, _fmt(cell)[:32], border=1)
            pdf.ln()
        pdf.ln(6)

    return bytes(pdf.output())


def render_excel(doc: ReportDocument) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = doc.title[:31] or "Report"

    header_font = Font(bold=True, size=14)
    subtitle_font = Font(size=10, italic=True, color="666666")
    section_font = Font(bold=True, size=12)
    table_header_font = Font(bold=True, color="FFFFFF")
    table_header_fill = PatternFill("solid", fgColor="0EA5E9")

    row = 1
    ws.cell(row=row, column=1, value=doc.title).font = header_font
    row += 1
    if doc.subtitle:
        ws.cell(row=row, column=1, value=doc.subtitle).font = subtitle_font
        row += 1
    ws.cell(row=row, column=1, value=f"Generated {doc.generated_at.strftime('%Y-%m-%d %H:%M UTC')}").font = subtitle_font
    row += 2

    for summary in doc.summaries:
        ws.cell(row=row, column=1, value=summary.heading).font = section_font
        row += 1
        for label, value in summary.items:
            ws.cell(row=row, column=1, value=label)
            cell = ws.cell(row=row, column=2, value=_fmt(value))
            cell.alignment = Alignment(horizontal="left")
            row += 1
        row += 1

    for table in doc.tables:
        ws.cell(row=row, column=1, value=table.heading).font = section_font
        row += 1
        for col_idx, col_name in enumerate(table.columns, start=1):
            cell = ws.cell(row=row, column=col_idx, value=col_name)
            cell.font = table_header_font
            cell.fill = table_header_fill
        row += 1
        for data_row in table.rows:
            for col_idx, value in enumerate(data_row, start=1):
                ws.cell(row=row, column=col_idx, value=_fmt(value))
            row += 1
        row += 2

    for col_idx in range(1, 12):
        ws.column_dimensions[get_column_letter(col_idx)].width = 20

    from io import BytesIO
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_csv(doc: ReportDocument) -> bytes:
    """CSV export — genuinely missing before (only PDF/Excel existed).
    One flat CSV: summary key/value pairs first (so the export is
    self-contained — a CSV opened alone still shows what it's a
    summary of), then every table with its own heading and header row.
    Uses Python's own csv module rather than hand-joining strings, so
    quoting/escaping of commas and quotes inside values is handled
    correctly for free."""
    import csv
    from io import StringIO

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([doc.title])
    if doc.subtitle:
        writer.writerow([doc.subtitle])
    writer.writerow([f"Generated {doc.generated_at.strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])

    for summary in doc.summaries:
        writer.writerow([summary.heading])
        for label, value in summary.items:
            writer.writerow([label, _fmt(value)])
        writer.writerow([])

    for table in doc.tables:
        writer.writerow([table.heading])
        writer.writerow(table.columns)
        for data_row in table.rows:
            writer.writerow([_fmt(v) for v in data_row])
        writer.writerow([])

    return buf.getvalue().encode("utf-8-sig")  # BOM so Excel opens Arabic/UTF-8 text correctly
