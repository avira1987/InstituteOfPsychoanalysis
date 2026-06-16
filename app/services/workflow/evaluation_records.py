"""Service D - Committee / Evaluation Records Service.

Replaces the log-only stub for evaluation/commission records, committee tasks
and confidential notes. Persisted under ``Student.extra_data``:

    evaluations        -> evaluation completions and scores
    commission_results -> commission/committee outcomes
    tasks              -> generated committee/evaluation tasks
    confidential       -> confidential reasons/opinions (still persisted)
    block_counter_locked -> bool
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    extra = C.student_extra(student)
    result = action_type

    if action_type in ("record_commission_result", "record_commission_result_in_student_portal"):
        rec = {
            "id": C.new_id(),
            "result": ctx.get("commission_result") or ctx.get("result") or ctx.get("decision"),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "recorded_at": C.now_iso(),
            "visible_in_portal": action_type.endswith("student_portal"),
        }
        results = list(extra.get("commission_results") or [])
        results.append(rec)
        extra["commission_results"] = results
        result = f"commission_result_recorded={rec['result']}"

    elif action_type == "record_evaluation_completion":
        rec = {
            "id": C.new_id(),
            "evaluator_id": ctx.get("evaluator_id") or ctx.get("supervisor_id"),
            "process_code": instance.process_code,
            "completed_at": C.now_iso(),
        }
        evals = list(extra.get("evaluations") or [])
        evals.append(rec)
        extra["evaluations"] = evals
        result = "evaluation_completion_recorded"

    elif action_type == "add_ta_score":
        score = ctx.get("ta_score") or ctx.get("score")
        rec = {
            "id": C.new_id(),
            "score": score,
            "process_code": instance.process_code,
            "added_at": C.now_iso(),
        }
        evals = list(extra.get("evaluations") or [])
        evals.append({"type": "ta_score", **rec})
        extra["evaluations"] = evals
        result = f"ta_score_added={score}"

    elif action_type in ("create_evaluation_task", "create_education_committee_task"):
        task = {
            "id": C.new_id(),
            "kind": "evaluation" if action_type == "create_evaluation_task" else "education_committee",
            "title_fa": action.get("title_fa") or ctx.get("task_title_fa") or action_type,
            "assignee_role": action.get("assignee_role") or ctx.get("assignee_role") or "committee",
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "status": "open",
            "created_at": C.now_iso(),
        }
        tasks = list(extra.get("tasks") or [])
        tasks.append(task)
        extra["tasks"] = tasks
        result = f"task_created kind={task['kind']} id={task['id']}"

    elif action_type == "lock_block_counter":
        extra["block_counter_locked"] = True
        extra["block_counter_locked_at"] = C.now_iso()
        result = "block_counter_locked"

    elif action_type in (
        "store_executive_advisory_opinion",
        "store_nezarat_recommendation",
        "store_rejection_reason_confidential",
    ):
        conf = dict(extra.get("confidential") or {})
        key = {
            "store_executive_advisory_opinion": "executive_advisory_opinion",
            "store_nezarat_recommendation": "nezarat_recommendation",
            "store_rejection_reason_confidential": "rejection_reason",
        }[action_type]
        conf[key] = {
            "text_fa": ctx.get(f"{key}_fa") or ctx.get("opinion_fa") or ctx.get("recommendation_fa")
            or ctx.get("reason_fa") or "",
            "stored_at": C.now_iso(),
            "process_code": instance.process_code,
        }
        extra["confidential"] = conf
        result = f"confidential_stored:{key}"

    else:
        C.record_event(instance, action_type, {"unhandled_in": "evaluation_records"})
        return f"evaluation_noop:{action_type}"

    C.commit_student_extra(student, extra)
    C.record_event(instance, action_type, {"result": result})
    return result
