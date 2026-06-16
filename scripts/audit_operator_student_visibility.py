#!/usr/bin/env python3
"""
ممیزی شکاف «مرحلهٔ اپراتور ↔ دید دانشجو» از روی metadata/processes.

  python scripts/audit_operator_student_visibility.py
  python scripts/audit_operator_student_visibility.py --out reports/operator_student_visibility_audit.json

خروجی: JSON با rows، prioritized_gaps (حداکثر ۱۵)، summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.meta.operator_student_visibility_audit import build_operator_student_visibility_report


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit operator states vs student-facing hints (metadata)")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "reports" / "operator_student_visibility_audit.json",
        help="Output JSON path (default: reports/operator_student_visibility_audit.json)",
    )
    args = ap.parse_args()
    report = build_operator_student_visibility_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\nWrote: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
