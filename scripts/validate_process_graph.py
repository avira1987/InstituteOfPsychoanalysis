"""Static reachability analysis of every process state machine.

Three failure modes make a process impossible to finish, and none of them are
visible until a real user gets stuck:

  dead_end    a non-terminal state with no outgoing transition
  unreachable a state that cannot be reached from the initial state
  no_exit     a process with no terminal state reachable from the start

A transition whose only trigger is `sla_breach` (or another system-only trigger)
still counts as an exit, but a state whose *only* exits are system triggers is
reported separately as `system_only_exit`: a human will sit there until a
scheduler happens to fire.

Usage:
    python -m scripts.validate_process_graph
    python -m scripts.validate_process_graph --json
    python -m scripts.validate_process_graph --process theory_course_completion
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSES_DIR = REPO_ROOT / "metadata" / "processes"

TERMINAL_STATE_TYPES = frozenset({"terminal", "final", "end"})

# Triggers no human can press from a portal.
SYSTEM_ONLY_TRIGGERS = frozenset(
    {
        "sla_breach",
        "timeout",
        "deadline_passed",
        "auto_advance",
        "scheduler_tick",
    }
)

# Escape hatches. Every entry needs a reason, and every reason is printed as a
# warning on each run so exceptions stay visible instead of becoming permanent.
# Keep these lists short: they are the difference between "known and accepted"
# and "silently broken".

# Non-terminal states advanced by a scheduler or webhook rather than by an
# outgoing metadata transition.
ALLOWED_DEAD_ENDS: dict[str, dict[str, str]] = {}

# States that cannot be reached from the initial state and are accepted as such.
ALLOWED_UNREACHABLE: dict[str, dict[str, str]] = {
    "introductory_course_registration": {
        "interview_scheduled": (
            "Deliberately bypassed on 2026-05-07: booking goes straight from "
            "application_submitted to interview_payment. The state is kept because "
            "engine.py and interview_slot_service.py still handle instances parked "
            "there, and it has a working proceed_to_payment exit."
        ),
    },
    "return_to_full_education": {
        "return_rejected": (
            "Rejection path is designed (StudentReturnToFullEducationPanel renders "
            "it) but no reviewer state exists yet to reject from. Wire this up in "
            "the leave/return phase, then delete this exemption."
        ),
    },
}


@dataclass
class ProcessGraph:
    code: str
    path: Path
    initial: Optional[str]
    states: dict[str, dict]
    outgoing: dict[str, list[dict]] = field(default_factory=dict)
    incoming: dict[str, list[dict]] = field(default_factory=dict)

    def is_terminal(self, state_code: str) -> bool:
        state = self.states.get(state_code) or {}
        return str(state.get("type", "")).lower() in TERMINAL_STATE_TYPES

    def reachable(self) -> set[str]:
        if not self.initial:
            return set()
        seen = {self.initial}
        queue = deque([self.initial])
        while queue:
            current = queue.popleft()
            for transition in self.outgoing.get(current, []):
                target = transition.get("to")
                if target and target not in seen:
                    seen.add(target)
                    queue.append(target)
        return seen


@dataclass
class ProcessReport:
    code: str
    state_count: int
    transition_count: int
    dead_ends: list[str] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    unknown_targets: list[str] = field(default_factory=list)
    system_only_exits: list[str] = field(default_factory=list)
    exempted: list[str] = field(default_factory=list)
    missing_initial: bool = False
    no_reachable_terminal: bool = False

    @property
    def errors(self) -> list[str]:
        problems: list[str] = []
        if self.missing_initial:
            problems.append("initial_state is missing or undefined")
        if self.no_reachable_terminal:
            problems.append("no terminal state reachable from the initial state")
        for state in self.dead_ends:
            problems.append(f"dead_end: '{state}' is non-terminal with no outgoing transition")
        for state in self.unreachable:
            problems.append(f"unreachable: '{state}' cannot be reached from the initial state")
        for ref in self.unknown_targets:
            problems.append(f"unknown_target: transition points at undefined state '{ref}'")
        return problems

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "process": self.code,
            "states": self.state_count,
            "transitions": self.transition_count,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": [
                f"system_only_exit: '{s}' can only be left by a system trigger"
                for s in self.system_only_exits
            ],
            "exemptions": self.exempted,
        }


def build_graph(path: Path) -> ProcessGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    process = data.get("process") or {}
    code = str(process.get("code") or path.stem)

    states = {
        str(state.get("code")): state
        for state in (data.get("states") or [])
        if isinstance(state, dict) and state.get("code")
    }

    graph = ProcessGraph(
        code=code,
        path=path,
        initial=process.get("initial_state") or process.get("initial_state_code"),
        states=states,
        outgoing=defaultdict(list),
        incoming=defaultdict(list),
    )

    for transition in data.get("transitions") or []:
        if not isinstance(transition, dict):
            continue
        source = transition.get("from")
        target = transition.get("to")
        if source:
            graph.outgoing[str(source)].append(transition)
        if target:
            graph.incoming[str(target)].append(transition)
    return graph


def analyze(graph: ProcessGraph) -> ProcessReport:
    transition_count = sum(len(v) for v in graph.outgoing.values())
    report = ProcessReport(
        code=graph.code,
        state_count=len(graph.states),
        transition_count=transition_count,
    )

    if not graph.initial or graph.initial not in graph.states:
        report.missing_initial = True
        return report

    reachable = graph.reachable()
    allowed_dead_ends = ALLOWED_DEAD_ENDS.get(graph.code, {})
    allowed_unreachable = ALLOWED_UNREACHABLE.get(graph.code, {})

    for state_code in graph.states:
        exits = graph.outgoing.get(state_code, [])
        if not exits and not graph.is_terminal(state_code):
            if state_code in allowed_dead_ends:
                report.exempted.append(f"dead_end '{state_code}': {allowed_dead_ends[state_code]}")
            else:
                report.dead_ends.append(state_code)
        if state_code not in reachable:
            if state_code in allowed_unreachable:
                report.exempted.append(
                    f"unreachable '{state_code}': {allowed_unreachable[state_code]}"
                )
            else:
                report.unreachable.append(state_code)
        if exits and not graph.is_terminal(state_code):
            triggers = {str(t.get("trigger") or "") for t in exits}
            if triggers and triggers <= SYSTEM_ONLY_TRIGGERS:
                report.system_only_exits.append(state_code)

    referenced = {
        str(t.get(key))
        for transitions in graph.outgoing.values()
        for t in transitions
        for key in ("from", "to")
        if t.get(key)
    }
    report.unknown_targets = sorted(referenced - set(graph.states))

    if not any(graph.is_terminal(state) for state in reachable):
        report.no_reachable_terminal = True

    report.dead_ends.sort()
    report.unreachable.sort()
    report.system_only_exits.sort()
    report.exempted.sort()
    return report


def analyze_all(
    processes_dir: Path = PROCESSES_DIR, only: Optional[str] = None
) -> list[ProcessReport]:
    reports = []
    for path in sorted(processes_dir.glob("*.json")):
        if only and path.stem != only:
            continue
        reports.append(analyze(build_graph(path)))
    return reports


def find_broken(processes_dir: Path = PROCESSES_DIR) -> list[ProcessReport]:
    return [report for report in analyze_all(processes_dir) if not report.ok]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--process", help="analyze a single process code")
    parser.add_argument(
        "--warnings", action="store_true", help="also print system-only-exit warnings"
    )
    args = parser.parse_args(argv)

    reports = analyze_all(only=args.process)
    broken = [r for r in reports if not r.ok]

    if args.json:
        print(
            json.dumps(
                {
                    "processes_analyzed": len(reports),
                    "broken": len(broken),
                    "ok": not broken,
                    "reports": [r.as_dict() for r in reports if not r.ok or args.warnings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if broken else 0

    print(f"processes analyzed : {len(reports)}")
    print(f"states analyzed    : {sum(r.state_count for r in reports)}")

    exempted = [r for r in reports if r.exempted]
    if exempted:
        total = sum(len(r.exempted) for r in exempted)
        print(f"\nACCEPTED EXCEPTIONS ({total}) - remove these as the gaps are closed:")
        for report in exempted:
            for note in report.exempted:
                print(f"  {report.code} / {note}")

    if args.warnings:
        warned = [r for r in reports if r.system_only_exits]
        if warned:
            print(f"\nWARNINGS - {len(warned)} process(es) have system-only exits:")
            for report in warned:
                print(f"  {report.code}: {', '.join(report.system_only_exits)}")

    if not broken:
        print("\nOK - every process is fully reachable with no dead ends.")
        return 0

    print(f"\nFAIL - {len(broken)} process(es) have an unreachable or dead-end graph:\n")
    for report in broken:
        print(f"  {report.code}")
        for problem in report.errors:
            print(f"      {problem}")
    return 1


if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))
    raise SystemExit(main())
