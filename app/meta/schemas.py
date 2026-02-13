"""Pydantic models for metadata JSON schemas."""

from typing import Optional, Any
from pydantic import BaseModel, Field
from uuid import UUID


# ─── Rule Schemas ──────────────────────────────────────────────

class RuleExpression(BaseModel):
    """A rule expression (can be recursive)."""
    field: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[Any] = None
    conditions: Optional[list["RuleExpression"]] = None
    condition: Optional["RuleExpression"] = None
    # Conditional
    if_: Optional["RuleExpression"] = Field(None, alias="if")
    then: Optional[Any] = None
    else_: Optional[Any] = Field(None, alias="else")
    # Formula
    formula: Optional[str] = None
    reset_cycle: Optional[str] = None

    model_config = {"populate_by_name": True}


class RuleSchema(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    rule_type: str = "condition"
    expression: dict
    parameters: Optional[dict] = None
    error_message_fa: Optional[str] = None
    action: Optional[str] = None


# ─── Action Schemas ────────────────────────────────────────────

class ActionSchema(BaseModel):
    type: str
    condition: Optional[str] = None
    message_fa: Optional[str] = None
    process_code: Optional[str] = None
    notification_type: Optional[str] = None
    recipients: Optional[list[str]] = None
    template: Optional[str] = None


# ─── Transition Schemas ────────────────────────────────────────

class TransitionSchema(BaseModel):
    from_state: str = Field(alias="from")
    to_state: str = Field(alias="to")
    trigger: str
    required_role: Optional[str] = None
    conditions: Optional[list[str]] = None
    actions: Optional[list[ActionSchema]] = None
    description_fa: Optional[str] = None
    priority: int = 0

    model_config = {"populate_by_name": True}


# ─── State Schemas ─────────────────────────────────────────────

class StateSchema(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    type: str = "intermediate"
    assigned_role: Optional[str] = None
    sla_hours: Optional[int] = None
    on_sla_breach_event: Optional[str] = None
    metadata_: Optional[dict] = Field(None, alias="metadata")

    model_config = {"populate_by_name": True}


# ─── Process Schemas ───────────────────────────────────────────

class ProcessSchema(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    initial_state: str
    config: Optional[dict] = None


class ProcessFileSchema(BaseModel):
    """Full process definition file schema."""
    process: ProcessSchema
    states: list[StateSchema]
    transitions: list[TransitionSchema]


# ─── Role Schemas ──────────────────────────────────────────────

class RoleSchema(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    permissions: list[str] = []
