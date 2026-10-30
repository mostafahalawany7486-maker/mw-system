"""
Enterprise Reporting extension: Export Scheduling.

Everything else this phase needed already existed and was extended in
place (ReportsService, AccountingReportService, the Attachment model for
storing generated files). A recurring "run this report on a schedule and
keep the export on file" configuration is the one concept nothing in the
existing schema represents, so it gets exactly one new table.

Honest scope note: there is no SMTP/email integration anywhere in this
codebase (confirmed during the i18n phase's audit), so a schedule does
not "email" anyone — it generates the export file on its due date (via a
manual "run now" trigger, or a batch check of due schedules) and stores
it as an Attachment (entity_type="report_schedule", entity_id=<this
schedule's id>) for download, exactly like every other generated/
uploaded file in this system. Wiring actual email delivery once SMTP
exists is a couple of lines in ReportScheduleService.run(), not a schema
change.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class ReportFrequency:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReportExportFormat:
    PDF = "pdf"
    EXCEL = "excel"


class ReportSchedule(BaseModel):
    __tablename__ = "report_schedules"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    export_format: Mapped[str] = mapped_column(String(10), nullable=False, default=ReportExportFormat.PDF)
    frequency: Mapped[str] = mapped_column(String(10), nullable=False, default=ReportFrequency.MONTHLY)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g. {"property_id": 3, "days": 30}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_export_attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attachments.id"), nullable=True)

    last_export_attachment: Mapped[Optional["Attachment"]] = relationship(foreign_keys=[last_export_attachment_id])  # noqa: F821

    @property
    def last_export_file_url(self) -> Optional[str]:
        return self.last_export_attachment.file_url if self.last_export_attachment else None

    @property
    def last_export_file_name(self) -> Optional[str]:
        return self.last_export_attachment.file_name if self.last_export_attachment else None
