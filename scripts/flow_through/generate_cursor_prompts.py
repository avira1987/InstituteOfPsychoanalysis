#!/usr/bin/env python3
"""Generate Cursor prompt markdown files from flow_through gaps.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.flow_through.common import GAPS_PATH, PROMPTS_DIR, matrix_paths_for_track


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", (s or "gap").strip())[:80]


def prompt_md(gap: dict) -> str:
    fields = gap.get("field_specs") or []
    field_lines = "\n".join(
        f"- `{f.get('name')}` ({f.get('type')}) — {f.get('label_fa')}"
        for f in fields[:20]
    )
    return f"""# Flow-Through Gap: {gap.get('process_code')} / {gap.get('state_code')}

## Context
- **Process:** `{gap.get('process_code')}`
- **State:** `{gap.get('state_code')}`
- **Role:** `{gap.get('required_role')}` → portal: `{gap.get('portal_role')}`
- **Trigger:** `{gap.get('trigger')}` → `{gap.get('to_state')}`
- **Failed at:** `{gap.get('failed_at')}` ({gap.get('layer')} layer)

## Error
```
{gap.get('detail', '')}
```

## Expected UI
- **Layer:** `{gap.get('ui_layer')}`
- **Component:** `{gap.get('ui_component') or 'TBD'}`

## Form fields (metadata)
{field_lines or '(no forms in metadata)'}

## Task
Build or fix UI so user with role `{gap.get('portal_role')}` can:
1. Open the correct portal/deep link for this state
2. See and fill the step form
3. Submit the form
4. Click transition `{gap.get('trigger')}` and reach `{gap.get('to_state')}`

## Acceptance criteria
- Add `data-testid`: `uf-field-{{name}}`, `operator-transition-{gap.get('trigger')}` or `quest-transition-{gap.get('to_state')}`
- API: `POST .../operator-step-forms/register` (or student variant) returns 200
- API: `POST .../trigger` with `{gap.get('trigger')}` succeeds
- Playwright flow-through test for this step passes
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Cursor prompts from gaps.json")
    ap.add_argument("--track", type=str, default=None)
    ap.add_argument("--in", dest="in_path", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    track = args.track or "wave1"
    _, _, gaps_path, prompts_dir = matrix_paths_for_track(track)
    in_path = args.in_path or gaps_path
    out_dir = args.out_dir or prompts_dir

    if not in_path.is_file():
        print(f"No gaps file: {in_path}", file=sys.stderr)
        return 1

    data = json.loads(in_path.read_text(encoding="utf-8"))
    gaps = data.get("gaps") or []
    out_dir.mkdir(parents=True, exist_ok=True)

    for gap in gaps:
        name = _slug(
            f"{gap.get('process_code')}_{gap.get('state_code')}_{gap.get('portal_role')}_{gap.get('failed_at')}"
        )
        path = out_dir / f"{name}.md"
        path.write_text(prompt_md(gap), encoding="utf-8")

    print(f"Wrote {len(gaps)} prompts -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
