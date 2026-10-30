"""
Shared response contract for the Business Workflow Layer.

A single workflow call can coordinate several existing services at once
(e.g. lease + financial + notifications), so every workflow method
returns a `WorkflowResult` — one predictable shape regardless of how many
subsystems were touched underneath. This mirrors, at the orchestration
level, what MessageResponse/PaginatedResponse already do for plain CRUD
responses in app/schemas/common.py.

Validation failures still raise `HTTPException`, exactly like every
service in app/services/*. `WorkflowResult` describes a *successful*
orchestration outcome, not an error channel — it does not replace
FastAPI's existing exception handling.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class WorkflowResult(BaseModel):
    """Standardized response returned by every business workflow method.

    Attributes:
        success: Always True when returned (failures raise HTTPException
            instead), kept explicit so a WorkflowResult is self-describing
            if logged, cached, or serialized on its own.
        workflow: Machine-readable name of the workflow that ran, e.g.
            "lease.activate_with_schedule" — useful for logging/telemetry.
        message: Human-readable summary of what happened.
        data: The primary result payload (an ORM object, dict, or list,
            depending on the workflow). Left untyped deliberately since
            this layer intentionally does not define its own response
            models beyond this envelope — API routers that expose a
            workflow can still map `data` onto the existing Pydantic
            schemas in app/schemas/* for their response_model.
        metrics: Dashboard-relevant counters gathered from the underlying
            services (e.g. counts returned by a service's dashboard() or
            outstanding_balances() method).
        notifications_sent: Number of in-app notifications dispatched by
            this workflow run.
        accounting_events: Human-readable log of accounting-relevant
            events this workflow triggered (e.g. "transaction TXN-000123
            posted"). Empty when a workflow had no financial impact.
        warnings: Non-fatal issues encountered while orchestrating (e.g.
            "renewal reminder skipped: no active superusers found").
    """

    model_config = {"arbitrary_types_allowed": True}

    success: bool = True
    workflow: str
    message: str
    data: Optional[Any] = None
    metrics: dict = Field(default_factory=dict)
    notifications_sent: int = 0
    accounting_events: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
