#!/usr/bin/env python3
"""Run full flow-through pipeline: matrix -> enrich -> gaps -> prompts."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Run flow-through pipeline")
    ap.add_argument("--wave", type=int, default=None)
    ap.add_argument("--track", type=str, default=None, help="wave1, wave2, or onboarding")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--proof", type=str, help="Limit pytest to one process code")
    args = ap.parse_args()

    track = args.track or (f"wave{args.wave}" if args.wave else "wave1")
    build_cmd = [sys.executable, "-m", "scripts.flow_through.build_matrix", "--track", track]
    enrich_cmd = [sys.executable, "-m", "scripts.flow_through.resolve_ui_surface", "--track", track]

    for cmd in (build_cmd, enrich_cmd):
        if _run(cmd) != 0:
            return 1

    if not args.skip_tests:
        env = os.environ.copy()
        env["FLOW_THROUGH_TRACK"] = track
        if args.proof:
            env["FLOW_THROUGH_PROOF"] = args.proof
        test_target = (
            "tests/flow_through/test_onboarding_flow.py"
            if track == "onboarding"
            else "tests/flow_through"
        )
        print(f"+ pytest {test_target}")
        r = subprocess.call(
            [sys.executable, "-m", "pytest", test_target, "-q", "--tb=short"],
            cwd=str(ROOT),
            env=env,
        )
        if r != 0:
            print("pytest reported failures (gaps may still be generated)")

    _run([sys.executable, "-m", "scripts.flow_through.report_gaps", "--track", track])
    _run([sys.executable, "-m", "scripts.flow_through.generate_cursor_prompts", "--track", track])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
