"""Reusable workflow action services.

Each module replaces the legacy ``_handle_external_integration`` stub for a
group of action types with real, domain-mutating behavior. State is persisted
to existing JSONB columns (``Student.extra_data`` / ``ProcessInstance.context_data``)
and real ORM columns, so no schema migration is required.

Modules:
    portal_notifications  - Service A: portal display, reminders, dashboard feeds
    lms_service           - Service B: enrollment, course unlock, attendance/links
    document_service      - Service C: certificates, transcripts, signed letters
    evaluation_records    - Service D: committee/evaluation records and tasks
    capacity_service      - Service E: capacity counters and assignment retention
    termination_records   - Service I: termination + accounting records
    calendar_service      - Service F: date-rule engine + calendar publishing
    registration_gate     - Service G: enrollment gate flags
    role_promotion        - Service H: role/rank promotion + account provisioning
"""

from app.services.workflow import (
    portal_notifications,
    lms_service,
    document_service,
    evaluation_records,
    capacity_service,
    termination_records,
    calendar_service,
    registration_gate,
    role_promotion,
)

__all__ = [
    "portal_notifications",
    "lms_service",
    "document_service",
    "evaluation_records",
    "capacity_service",
    "termination_records",
    "calendar_service",
    "registration_gate",
    "role_promotion",
]
