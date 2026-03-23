"""Metadata Loader - Loads process/rule definitions from database at runtime."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition, RuleDefinition


class MetadataLoader:
    """Loads metadata definitions from the database for runtime use."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load_process(self, process_code: str) -> Optional[dict]:
        """Load a complete process definition with states and transitions."""
        stmt = (
            select(ProcessDefinition)
            .options(
                selectinload(ProcessDefinition.states),
                selectinload(ProcessDefinition.transitions),
            )
            .where(
                ProcessDefinition.code == process_code,
                ProcessDefinition.is_active == True,
            )
        )
        result = await self.db.execute(stmt)
        process = result.scalars().first()
        if not process:
            return None

        return {
            "process": {
                "id": str(process.id),
                "code": process.code,
                "name_fa": process.name_fa,
                "initial_state": process.initial_state_code,
                "version": process.version,
                "config": process.config,
                "ui_requirements": (process.config or {}).get("ui_requirements", {}),
            },
            "states": [
                {
                    "code": s.code,
                    "name_fa": s.name_fa,
                    "type": s.state_type,
                    "assigned_role": s.assigned_role,
                    "sla_hours": s.sla_hours,
                    "on_sla_breach_event": s.on_sla_breach_event,
                }
                for s in process.states
            ],
            "transitions": [
                {
                    "from": t.from_state_code,
                    "to": t.to_state_code,
                    "trigger": t.trigger_event,
                    "required_role": t.required_role,
                    "conditions": t.condition_rules,
                    "actions": t.actions,
                    "priority": t.priority,
                }
                for t in process.transitions
            ],
        }

    async def load_all_processes(self) -> list[dict]:
        """Load summary of all active processes."""
        stmt = select(ProcessDefinition).where(ProcessDefinition.is_active == True)
        result = await self.db.execute(stmt)
        processes = result.scalars().all()
        return [
            {
                "id": str(p.id),
                "code": p.code,
                "name_fa": p.name_fa,
                "name_en": p.name_en,
                "version": p.version,
                "initial_state": p.initial_state_code,
            }
            for p in processes
        ]

    async def load_rule(self, rule_code: str) -> Optional[dict]:
        """Load a single rule definition."""
        stmt = select(RuleDefinition).where(
            RuleDefinition.code == rule_code,
            RuleDefinition.is_active == True,
        )
        result = await self.db.execute(stmt)
        rule = result.scalars().first()
        if not rule:
            return None
        return {
            "code": rule.code,
            "name_fa": rule.name_fa,
            "rule_type": rule.rule_type,
            "expression": rule.expression,
            "parameters": rule.parameters,
            "error_message_fa": rule.error_message_fa,
        }

    async def load_all_rules(self) -> list[dict]:
        """Load all active rules."""
        stmt = select(RuleDefinition).where(RuleDefinition.is_active == True)
        result = await self.db.execute(stmt)
        rules = result.scalars().all()
        return [
            {
                "code": r.code,
                "name_fa": r.name_fa,
                "rule_type": r.rule_type,
                "expression": r.expression,
                "parameters": r.parameters,
                "error_message_fa": r.error_message_fa,
                "version": r.version,
            }
            for r in rules
        ]
