"""اسنپ‌شات منابع میزبان/کانتینر بدون psutil — فقط با /proc و shutil.

روی Linux مقادیر واقعی (load avg، RAM کانتینر، RSS فرایند، دیسک ریشه)؛
روی Windows/سکوهای بدون /proc، فیلدهای غیرقابل‌اندازه‌گیری None برمی‌گردند تا UI گرepicful گزارش دهد.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

_PROC = Path("/proc")


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _parse_meminfo(text: str) -> dict[str, int]:
    """مقادیر /proc/meminfo را به بایت تبدیل می‌کند (کلیدها به همان نام proc)."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        rest = rest.strip()
        if not rest:
            continue
        parts = rest.split()
        try:
            num = int(parts[0])
        except (ValueError, IndexError):
            continue
        unit = parts[1].lower() if len(parts) > 1 else "b"
        if unit == "kb":
            num *= 1024
        elif unit == "mb":
            num *= 1024 * 1024
        out[key.strip()] = num
    return out


def _read_loadavg() -> tuple[float, float, float] | None:
    text = _read_text(_PROC / "loadavg")
    if not text:
        return None
    parts = text.strip().split()
    if len(parts) < 3:
        return None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None


def _cgroup_v2_mem_limit() -> int | None:
    """سقف حافظهٔ cgroup v2 (در Docker مدرن استفاده می‌شود)."""
    text = _read_text(Path("/sys/fs/cgroup/memory.max"))
    if not text:
        return None
    text = text.strip()
    if text == "max":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _cgroup_v2_mem_current() -> int | None:
    text = _read_text(Path("/sys/fs/cgroup/memory.current"))
    if not text:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def _cgroup_v1_mem_limit() -> int | None:
    text = _read_text(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"))
    if not text:
        return None
    try:
        v = int(text.strip())
    except ValueError:
        return None
    if v >= (1 << 62):
        return None
    return v


def _cgroup_v1_mem_usage() -> int | None:
    text = _read_text(Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"))
    if not text:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def _container_memory() -> dict[str, int | None]:
    """حافظهٔ کانتینر از cgroup (محدودیت Docker mem_limit)."""
    limit = _cgroup_v2_mem_limit()
    used = _cgroup_v2_mem_current()
    if limit is None and used is None:
        limit = _cgroup_v1_mem_limit()
        used = _cgroup_v1_mem_usage()
    return {"limit_bytes": limit, "used_bytes": used}


def _process_rss() -> int | None:
    text = _read_text(_PROC / "self" / "status")
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1]) * 1024
                except ValueError:
                    return None
    return None


def _disk_usage(path: str = "/") -> dict[str, int] | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}


def _cpu_count() -> int:
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


def collect_resource_snapshot() -> dict[str, Any]:
    """جمع‌آوری همهٔ متریک‌های قابل‌اندازه‌گیری در یک ساختار JSON-friendly."""
    snap: dict[str, Any] = {
        "timestamp": int(time.time()),
        "platform_supported": _PROC.exists(),
        "cpu_count": _cpu_count(),
    }

    load = _read_loadavg()
    if load is not None:
        cpu = snap["cpu_count"] or 1
        snap["load_average"] = {
            "one": load[0],
            "five": load[1],
            "fifteen": load[2],
            "one_pct": round((load[0] / cpu) * 100, 1),
            "five_pct": round((load[1] / cpu) * 100, 1),
            "fifteen_pct": round((load[2] / cpu) * 100, 1),
        }
    else:
        snap["load_average"] = None

    meminfo_text = _read_text(_PROC / "meminfo")
    if meminfo_text:
        m = _parse_meminfo(meminfo_text)
        total = m.get("MemTotal")
        avail = m.get("MemAvailable") or (m.get("MemFree", 0) + m.get("Buffers", 0) + m.get("Cached", 0))
        used = (total - avail) if (total is not None and avail is not None) else None
        snap["host_memory"] = {
            "total_bytes": total,
            "available_bytes": avail,
            "used_bytes": used,
            "used_pct": round((used / total) * 100, 1) if (total and used is not None) else None,
        }
    else:
        snap["host_memory"] = None

    cm = _container_memory()
    if cm["limit_bytes"] or cm["used_bytes"] is not None:
        used_pct: float | None = None
        if cm["limit_bytes"] and cm["used_bytes"] is not None and cm["limit_bytes"] > 0:
            used_pct = round((cm["used_bytes"] / cm["limit_bytes"]) * 100, 1)
        snap["container_memory"] = {**cm, "used_pct": used_pct}
    else:
        snap["container_memory"] = None

    snap["api_process_rss_bytes"] = _process_rss()

    snap["disk_root"] = _disk_usage("/")

    return snap
