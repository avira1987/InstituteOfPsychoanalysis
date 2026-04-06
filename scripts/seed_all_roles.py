#!/usr/bin/env python3
"""Wrapper: منطق در app/seed_all_roles.py و app/demo_role_users.py."""

import asyncio
import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.seed_all_roles import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
