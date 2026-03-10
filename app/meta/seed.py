"""Seed Script - Loads SOP-based metadata JSON files into the database."""

import json
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine, Base
from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition, RuleDefinition

logger = logging.getLogger(__name__)

METADATA_DIR = Path(__file__).parent.parent.parent / "metadata"


def get_rule_codes_from_rules_file() -> Set[str]:
    """Return set of rule codes defined in metadata/rules/all_rules.json."""
    rules_file = METADATA_DIR / "rules" / "all_rules.json"
    if not rules_file.exists():
        return set()
    with open(rules_file, "r", encoding="utf-8") as f:
        rules_data = json.load(f)
    return {r.get("code") for r in rules_data if r.get("code")}


def get_condition_codes_from_processes(processes_dir: Path) -> Dict[str, List[str]]:
    """
    Scan all process JSONs and return dict: process_code -> list of condition codes
    used in transitions (transition['conditions']).
    """
    process_conditions: Dict[str, List[str]] = {}
    if not processes_dir.exists():
        return process_conditions
    for process_file in processes_dir.glob("*.json"):
        try:
            with open(process_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skip %s: %s", process_file.name, e)
            continue
        proc_code = data.get("process", {}).get("code")
        if not proc_code:
            continue
        codes: List[str] = []
        for trans in data.get("transitions", []):
            for c in trans.get("conditions") or []:
                if isinstance(c, str):
                    codes.append(c)
        if codes:
            process_conditions[proc_code] = codes
    return process_conditions


def validate_process_rules(processes_dir: Path, rule_codes: Set[str]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Ensure every condition referenced in any process exists in rule_codes.
    Returns (list of "process_code: missing_rule_code", process_conditions dict).
    """
    process_conditions = get_condition_codes_from_processes(processes_dir)
    missing: List[str] = []
    for proc_code, codes in process_conditions.items():
        for c in codes:
            if c not in rule_codes:
                missing.append(f"{proc_code}: {c}")
    return missing, process_conditions


async def load_rules(db: AsyncSession):
    """Load all rule definitions from JSON file."""
    rules_file = METADATA_DIR / "rules" / "all_rules.json"
    if not rules_file.exists():
        logger.warning(f"Rules file not found: {rules_file}")
        return

    with open(rules_file, "r", encoding="utf-8") as f:
        rules_data = json.load(f)

    count = 0
    for rule in rules_data:
        rule_def = RuleDefinition(
            id=uuid.uuid4(),
            code=rule["code"],
            name_fa=rule["name_fa"],
            name_en=rule.get("name_en"),
            rule_type=rule.get("rule_type", "condition"),
            expression=rule["expression"],
            parameters=rule.get("parameters"),
            error_message_fa=rule.get("error_message_fa"),
            is_active=True,
            version=1,
        )
        db.add(rule_def)
        count += 1

    logger.info(f"Loaded {count} rule definitions")


async def sync_rules(db: AsyncSession) -> int:
    """Add only missing rules from all_rules.json. Returns count of added rules."""
    from sqlalchemy import select

    rules_file = METADATA_DIR / "rules" / "all_rules.json"
    if not rules_file.exists():
        logger.warning(f"Rules file not found: {rules_file}")
        return 0

    with open(rules_file, "r", encoding="utf-8") as f:
        rules_data = json.load(f)

    result = await db.execute(select(RuleDefinition.code))
    existing_codes = set(result.scalars().all())

    added = 0
    for rule in rules_data:
        code = rule.get("code")
        if not code or code in existing_codes:
            continue
        rule_def = RuleDefinition(
            id=uuid.uuid4(),
            code=code,
            name_fa=rule["name_fa"],
            name_en=rule.get("name_en"),
            rule_type=rule.get("rule_type", "condition"),
            expression=rule["expression"],
            parameters=rule.get("parameters"),
            error_message_fa=rule.get("error_message_fa"),
            is_active=True,
            version=1,
        )
        db.add(rule_def)
        existing_codes.add(code)
        added += 1

    if added:
        logger.info(f"Synced {added} new rule(s)")
    return added


async def load_process(db: AsyncSession, process_file: Path):
    """Load a process definition from a JSON file."""
    with open(process_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    proc_data = data["process"]
    process_id = uuid.uuid4()

    # Create process definition
    process_def = ProcessDefinition(
        id=process_id,
        code=proc_data["code"],
        name_fa=proc_data["name_fa"],
        name_en=proc_data.get("name_en"),
        description=proc_data.get("description"),
        version=1,
        is_active=True,
        initial_state_code=proc_data["initial_state"],
        config=proc_data.get("config"),
    )
    db.add(process_def)

    # Create state definitions
    for state in data.get("states", []):
        state_def = StateDefinition(
            id=uuid.uuid4(),
            process_id=process_id,
            code=state["code"],
            name_fa=state["name_fa"],
            name_en=state.get("name_en"),
            state_type=state.get("type", "intermediate"),
            metadata_=state.get("metadata"),
            assigned_role=state.get("assigned_role"),
            sla_hours=state.get("sla_hours"),
            on_sla_breach_event=state.get("on_sla_breach_event"),
        )
        db.add(state_def)

    # Create transition definitions
    for trans in data.get("transitions", []):
        actions = None
        if trans.get("actions"):
            actions = [
                a if isinstance(a, dict) else {"type": str(a)}
                for a in trans["actions"]
            ]

        trans_def = TransitionDefinition(
            id=uuid.uuid4(),
            process_id=process_id,
            from_state_code=trans["from"],
            to_state_code=trans["to"],
            trigger_event=trans["trigger"],
            condition_rules=trans.get("conditions"),
            required_role=trans.get("required_role"),
            actions=actions,
            priority=trans.get("priority", 0),
            description_fa=trans.get("description_fa"),
        )
        db.add(trans_def)

    logger.info(f"Loaded process: {proc_data['code']} ({proc_data['name_fa']})")


async def seed_all():
    """Seed all metadata into the database."""
    processes_dir = METADATA_DIR / "processes"
    rule_codes = get_rule_codes_from_rules_file()
    missing, _ = validate_process_rules(processes_dir, rule_codes)
    if missing:
        msg = (
            "فرایند و قوانین همگام نیستند. هر condition در transitionها باید در metadata/rules/all_rules.json تعریف شود. "
            "قوانین گم‌شده: " + ", ".join(missing)
        )
        logger.error(msg)
        raise ValueError(msg)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        try:
            # Load rules first
            await load_rules(db)

            # Load all process files
            if processes_dir.exists():
                for process_file in sorted(processes_dir.glob("*.json")):
                    await load_process(db, process_file)

            await db.commit()
            logger.info("Seed completed successfully!")

        except Exception as e:
            await db.rollback()
            logger.error("Seed failed: %s", e, exc_info=True)
            raise


async def clear_and_reseed():
    """Clear all metadata and re-seed from JSON files."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await seed_all()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_all())
