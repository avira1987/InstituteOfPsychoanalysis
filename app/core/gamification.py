"""Visible gamification: level, rank titles, badges — synced to student.extra_data['gamification']."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

GAMIFICATION_VERSION = 1

XP_PER_LEVEL = 100
MAX_LEVEL = 99

# (min_level inclusive, title_fa) — از بالا به پایین اولین تطابق
RANK_BY_LEVEL: list[tuple[int, str]] = [
    (50, "افسانهٔ مسیر آموزشی"),
    (35, "استاد مسیر انیستیتو"),
    (20, "ستارهٔ پیشرفت"),
    (12, "پیشرو"),
    (6, "کاوشگر مسیر"),
    (2, "رهرو تازه‌کار"),
    (1, "دانشجوی تازه‌کار"),
]


def rank_title_for_level(level: int) -> str:
    for min_lv, title in RANK_BY_LEVEL:
        if level >= min_lv:
            return title
    return RANK_BY_LEVEL[-1][1]


# هر مدال: id، عنوان، توضیح، و تابع شرط روی (total_xp, instances_dict)
BADGE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "id": "first_spark",
        "title_fa": "اولین جرقه",
        "description_fa": "اولین قدم را در مسیر فرایند برداشتید.",
        "emoji": "✨",
        "check": "xp15",
    },
    {
        "id": "bronze_trail",
        "title_fa": "مسیر برنزی",
        "description_fa": "به ۱۰۰ امتیاز تجربه رسیدید.",
        "emoji": "🥉",
        "check": "xp100",
    },
    {
        "id": "silver_trail",
        "title_fa": "مسیر نقره‌ای",
        "description_fa": "به ۳۰۰ امتیاز تجربه رسیدید.",
        "emoji": "🥈",
        "check": "xp300",
    },
    {
        "id": "gold_trail",
        "title_fa": "مسیر طلایی",
        "description_fa": "به ۸۰۰ امتیاز تجربه رسیدید.",
        "emoji": "🥇",
        "check": "xp800",
    },
    {
        "id": "dual_path",
        "title_fa": "دو مسیر",
        "description_fa": "حداقل دو فرایند فعال یا گذشته در کارنامهٔ شما ثبت شده است.",
        "emoji": "🔀",
        "check": "instances2",
    },
    {
        "id": "polyglot_process",
        "title_fa": "چندفراینده",
        "description_fa": "حداقل سه نوع فرایند مختلف را تجربه کرده‌اید.",
        "emoji": "🎯",
        "check": "process3",
    },
    {
        "id": "marathon",
        "title_fa": "استقامت",
        "description_fa": "به ۱۵۰۰ امتیاز تجربه رسیدید.",
        "emoji": "🏃",
        "check": "xp1500",
    },
]


def _check_condition(check: str, total_xp: int, instances: dict[str, Any]) -> bool:
    codes = {str(v.get("process_code") or "") for v in instances.values() if v.get("process_code")}
    n_inst = len(instances)
    if check == "xp15":
        return total_xp >= 15
    if check == "xp100":
        return total_xp >= 100
    if check == "xp300":
        return total_xp >= 300
    if check == "xp800":
        return total_xp >= 800
    if check == "xp1500":
        return total_xp >= 1500
    if check == "instances2":
        return n_inst >= 2
    if check == "process3":
        return len(codes) >= 3
    return False


def compute_gamification_snapshot(extra_data: dict[str, Any] | None) -> dict[str, Any]:
    """Build full gamification payload for extra_data['gamification']."""
    extra = dict(extra_data or {})
    hp = dict(extra.get("hidden_progress") or {})
    total_xp = int(hp.get("total_xp", 0))
    instances = dict(hp.get("instances") or {})

    level = min(MAX_LEVEL, max(1, 1 + total_xp // XP_PER_LEVEL))
    xp_in_level = total_xp % XP_PER_LEVEL
    xp_to_next = XP_PER_LEVEL - xp_in_level if level < MAX_LEVEL else 0
    rank_title = rank_title_for_level(level)

    prev_g = dict(extra.get("gamification") or {})
    earned_at: dict[str, str] = dict(prev_g.get("badge_earned_at") or {})
    now = datetime.now(timezone.utc).isoformat()

    badges_out: list[dict[str, Any]] = []
    for bd in BADGE_DEFINITIONS:
        earned = _check_condition(bd["check"], total_xp, instances)
        bid = bd["id"]
        if earned and bid not in earned_at:
            earned_at[bid] = now
        badges_out.append(
            {
                "id": bid,
                "title_fa": bd["title_fa"],
                "description_fa": bd["description_fa"],
                "emoji": bd["emoji"],
                "earned": earned,
                "earned_at": earned_at.get(bid),
            }
        )

    earned_count = sum(1 for b in badges_out if b["earned"])
    total_badges = len(badges_out)

    return {
        "version": GAMIFICATION_VERSION,
        "level": level,
        "total_xp": total_xp,
        "xp_in_current_level": xp_in_level,
        "xp_to_next_level": xp_to_next,
        "xp_per_level": XP_PER_LEVEL,
        "rank_title_fa": rank_title,
        "badges": badges_out,
        "badge_earned_at": earned_at,
        "stats": {
            "badges_earned": earned_count,
            "badges_total": total_badges,
        },
    }


def merge_gamification_into_extra(student_extra_data: dict[str, Any] | None) -> dict[str, Any]:
    """Return new extra_data dict with gamification key updated."""
    extra = dict(student_extra_data or {})
    snap = compute_gamification_snapshot(extra)
    extra["gamification"] = snap
    return extra
