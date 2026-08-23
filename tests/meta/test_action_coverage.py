"""Every action type in process metadata must resolve to a real handler.

`ActionHandler._dispatch` treats an unknown action type as a warning and reports
the transition as successful, so a typo or an unimplemented action is invisible
at runtime. This suite is the only place that failure mode is loud.
"""

import json

import pytest

from app.services.action_handler import ActionHandler
from scripts.validate_action_coverage import (
    PROCESSES_DIR,
    collect_usages,
    find_unhandled,
    is_handled,
    known_action_types,
)


def test_no_metadata_action_type_is_unhandled():
    unhandled = find_unhandled()
    assert not unhandled, (
        "action types used in metadata/processes/*.json with no handler: "
        + json.dumps({k: v[:3] for k, v in unhandled.items()}, ensure_ascii=False)
    )


def test_every_action_has_a_type():
    assert "<missing type>" not in collect_usages(), "some action objects lack a 'type' key"


def test_start_sub_process_is_registered():
    """Regression: this spelling silently no-op'd in four course-completion processes."""
    assert "start_sub_process" in known_action_types()


@pytest.mark.parametrize(
    "process_code",
    [
        "theory_course_completion",
        "skills_course_completion",
        "group_supervision_course_completion",
        "live_supervision_course_completion",
    ],
)
def test_course_completion_actions_all_resolve(process_code):
    """The four processes the acceptance audit flagged as unable to complete."""
    path = PROCESSES_DIR / f"{process_code}.json"
    definition = json.loads(path.read_text(encoding="utf-8"))
    registry = known_action_types()

    unresolved = [
        action.get("type")
        for transition in definition.get("transitions") or []
        for action in transition.get("actions") or []
        if isinstance(action, dict) and not is_handled(str(action.get("type")), registry)
    ]
    assert not unresolved, f"{process_code} has unhandled actions: {sorted(set(unresolved))}"


async def test_start_sub_process_normalizes_to_start_process():
    """`sub_process_code` must be forwarded as `process_code`."""
    captured = {}

    async def fake_start_process(action, instance, context):
        captured.update(action)
        return "ok"

    handler = ActionHandler.__new__(ActionHandler)
    handler._handle_start_process = fake_start_process

    result = await ActionHandler._handle_start_sub_process(
        handler,
        {"type": "start_sub_process", "sub_process_code": "violation_registration"},
        None,
        {},
    )
    assert result == "ok"
    assert captured["process_code"] == "violation_registration"
    assert captured["type"] == "start_process"


async def test_start_sub_process_prefers_sub_process_code_over_process_code():
    captured = {}

    async def fake_start_process(action, instance, context):
        captured.update(action)
        return "ok"

    handler = ActionHandler.__new__(ActionHandler)
    handler._handle_start_process = fake_start_process

    await ActionHandler._handle_start_sub_process(
        handler,
        {"sub_process_code": "violation_registration", "process_code": "stale"},
        None,
        {},
    )
    assert captured["process_code"] == "violation_registration"


async def test_start_sub_process_without_target_raises():
    handler = ActionHandler.__new__(ActionHandler)
    with pytest.raises(ValueError, match="sub_process_code"):
        await ActionHandler._handle_start_sub_process(
            handler, {"type": "start_sub_process"}, None, {}
        )
