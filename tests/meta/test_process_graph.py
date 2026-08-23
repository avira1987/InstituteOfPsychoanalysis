"""Every process state machine must be finishable.

A dead-end state or an unreachable state is invisible until a real user is stuck
in it, so the graph is checked statically here. Accepted exceptions live in
`scripts.validate_process_graph.ALLOWED_DEAD_ENDS` / `ALLOWED_UNREACHABLE` and
each one carries a written reason.
"""

import pytest

from scripts.validate_process_graph import (
    ALLOWED_DEAD_ENDS,
    ALLOWED_UNREACHABLE,
    PROCESSES_DIR,
    analyze,
    analyze_all,
    build_graph,
)

ALL_REPORTS = {report.code: report for report in analyze_all()}
PROCESS_CODES = sorted(ALL_REPORTS)


def test_there_are_processes_to_analyze():
    assert len(PROCESS_CODES) > 70, f"only found {len(PROCESS_CODES)} processes"


@pytest.mark.parametrize("process_code", PROCESS_CODES)
def test_process_graph_is_sound(process_code):
    report = ALL_REPORTS[process_code]
    assert report.ok, f"{process_code}: " + "; ".join(report.errors)


@pytest.mark.parametrize("process_code", PROCESS_CODES)
def test_every_process_can_finish(process_code):
    """At least one terminal state must be reachable from the initial state."""
    report = ALL_REPORTS[process_code]
    assert not report.no_reachable_terminal, f"{process_code} can never reach a terminal state"


def test_no_transition_points_at_an_undefined_state():
    offenders = {
        code: report.unknown_targets for code, report in ALL_REPORTS.items() if report.unknown_targets
    }
    assert not offenders, f"transitions reference undefined states: {offenders}"


# ─── regressions the acceptance audit flagged ───────────────────────


@pytest.mark.parametrize(
    "process_code",
    ["theory_course_completion", "skills_course_completion", "upgrade_to_educational_therapist"],
)
def test_previously_stuck_processes_have_no_dead_ends(process_code):
    assert not ALL_REPORTS[process_code].dead_ends


def test_grades_computed_state_is_gone():
    """It was orphaned in both directions; grade computation is an action, not a state."""
    for process_code in ("theory_course_completion", "skills_course_completion"):
        graph = build_graph(PROCESSES_DIR / f"{process_code}.json")
        assert "grades_computed" not in graph.states, (
            f"{process_code} reintroduced the orphan 'grades_computed' state"
        )


def test_therapy_frequency_escalation_has_a_way_out():
    graph = build_graph(PROCESSES_DIR / "upgrade_to_educational_therapist.json")
    exits = {t["to"] for t in graph.outgoing.get("therapy_frequency_escalation", [])}
    assert exits, "therapy_frequency_escalation is a dead end again"
    assert "personal_therapy_hours" in exits, "no path forward after the committee follows up"
    assert "eligibility_failed" in exits, "no way to close an upgrade that never complied"


def test_process_merged_to_one_redirects_to_educational_leave():
    """SOP 58 was merged into SOP 1; the stub must hand off, not loop forever."""
    graph = build_graph(PROCESSES_DIR / "process_merged_to_one.json")
    report = analyze(graph)
    assert not report.no_reachable_terminal

    targets = {
        action.get("process_code")
        for transitions in graph.outgoing.values()
        for transition in transitions
        for action in transition.get("actions") or []
        if isinstance(action, dict) and action.get("type") == "start_process"
    }
    assert "educational_leave" in targets


# ─── the exemption allowlist must stay honest ───────────────────────


def test_exemptions_all_carry_a_reason():
    for table in (ALLOWED_DEAD_ENDS, ALLOWED_UNREACHABLE):
        for process_code, states in table.items():
            for state, reason in states.items():
                assert reason and len(reason) > 30, (
                    f"{process_code}/{state} needs a real explanation, not '{reason}'"
                )


def test_exemptions_refer_to_states_that_exist():
    """A stale exemption silently weakens the check for a state that is long gone."""
    for table in (ALLOWED_DEAD_ENDS, ALLOWED_UNREACHABLE):
        for process_code, states in table.items():
            graph = build_graph(PROCESSES_DIR / f"{process_code}.json")
            unknown = sorted(set(states) - set(graph.states))
            assert not unknown, f"{process_code} has exemptions for missing states: {unknown}"


def test_exemptions_are_still_needed():
    """If a gap got fixed, the exemption must be deleted rather than left behind."""
    for process_code, states in ALLOWED_UNREACHABLE.items():
        graph = build_graph(PROCESSES_DIR / f"{process_code}.json")
        reachable = graph.reachable()
        stale = sorted(state for state in states if state in reachable)
        assert not stale, (
            f"{process_code}: {stale} are reachable now — remove them from ALLOWED_UNREACHABLE"
        )
