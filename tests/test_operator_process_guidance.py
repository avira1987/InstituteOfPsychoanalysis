"""Smoke: run scripts/test_operator_guidance.mjs via node subprocess."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_operator_guidance_node_smoke():
    node = shutil.which("node")
    assert node, "node not found on PATH"
    script = ROOT / "scripts" / "test_operator_guidance.mjs"
    proc = subprocess.run(
        [node, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
