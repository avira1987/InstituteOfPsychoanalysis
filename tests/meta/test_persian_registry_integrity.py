"""Registry / metadata Persian text must not have stripped connecting letters."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.persian_text_integrity import (  # noqa: E402
    is_stripped_persian,
    iter_fa_strings,
    try_prefix_repair,
)

INDEX_PATH = ROOT / "metadata" / "process_registry" / "INDEX.json"
PROCESSES_DIR = ROOT / "metadata" / "processes"
REGISTRY_DIR = ROOT / "metadata" / "process_registry" / "processes"
SUMMARY_PATH = ROOT / "_process_map_summary.md"
SOP_SAMPLES = (
    "start_therapy",
    "therapy_changes",
    "educational_leave",
    "introductory_course_registration",
)


def test_detector_flags_known_stripped_samples():
    assert is_stripped_persian("آغاز درا آزش")
    assert is_stripped_persian("درت تغرات درا آزش")
    assert is_stripped_persian("فرست فرادا ثبتشد  بع حت برا ضعت  تکا")
    assert is_stripped_persian("اطاعرسا شرط شرع درا شخص")
    assert is_stripped_persian("رح ۲۹. گام آزمایشی")
    assert is_stripped_persian("مرحله ۶۱ (SOP). جس۱۸ شارکت تا ۲۴:۰۰ ارزاب کف ظارت")
    assert is_stripped_persian("مرحله ۲۴ (سخ برز SOP). سر اف: ک جس در فت")


def test_detector_allows_healthy_persian():
    assert not is_stripped_persian("آغاز درمان آموزشی")
    assert not is_stripped_persian("فهرست ماشین‌خوان فرایندها و وضعیت آن‌ها")
    assert not is_stripped_persian(
        "بدون تأیید درمانگر: therapist_selected → book اسلات‌های شیت کمیته"
    )
    assert not is_stripped_persian("کمیته نظارت مشارکت جبرانی و تخلف آموزشی")
    assert not is_stripped_persian("ثبت تخلفات")
    assert not is_stripped_persian("آغاز هر درس در هر ترم")
    assert not is_stripped_persian("ثبت بسته شده")


def test_prefix_repair_restores_marhale_and_beruz():
    assert try_prefix_repair("رح ۲۹. مکان کلاس اختیاری است.").startswith("مرحله ۲۹")
    assert "به‌روز" in try_prefix_repair("مرحله ۴۰ (SOP برز). تعلیق و مرخصی")


def test_index_description_name_fa_and_notes_are_intact():
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    if is_stripped_persian(data.get("description")):
        failures.append("INDEX.description")
    for proc in data.get("processes") or []:
        code = proc.get("code") or "?"
        if is_stripped_persian(proc.get("name_fa")):
            failures.append(f"{code}.name_fa")
        if is_stripped_persian(proc.get("notes")):
            failures.append(f"{code}.notes")
    assert not failures, "stripped Persian in INDEX.json: " + ", ".join(failures[:30])


def test_process_metadata_name_and_description_fa_intact():
    failures: list[str] = []
    for path in sorted(PROCESSES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for loc, text in iter_fa_strings(data, keys=frozenset({"name_fa", "description_fa"})):
            if is_stripped_persian(text):
                failures.append(f"{path.name}:{loc}")
    assert not failures, "stripped Persian in metadata/processes: " + ", ".join(failures[:40])


def test_registry_03_output_name_and_description_fa_intact():
    failures: list[str] = []
    for path in sorted(REGISTRY_DIR.glob("*/03_output.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for loc, text in iter_fa_strings(data, keys=frozenset({"name_fa", "description_fa"})):
            if is_stripped_persian(text):
                failures.append(f"{path.parent.name}/03_output.json:{loc}")
    assert not failures, "stripped Persian in 03_output.json: " + ", ".join(failures[:40])


def test_process_map_summary_name_fa_lines_intact():
    assert SUMMARY_PATH.is_file(), f"missing {SUMMARY_PATH.name}; generate it first"
    failures: list[str] = []
    for i, line in enumerate(SUMMARY_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.startswith("- Name (fa):"):
            continue
        value = line.split(":", 1)[1].strip()
        if is_stripped_persian(value):
            failures.append(f"L{i}:{value}")
    assert not failures, "stripped Persian in _process_map_summary.md: " + ", ".join(failures[:20])


def test_sop_documents_remain_healthy():
    for code in SOP_SAMPLES:
        path = REGISTRY_DIR / code / "SOP_document.txt"
        text = path.read_text(encoding="utf-8")
        assert not is_stripped_persian(text[:400]), f"{code} SOP looks stripped"
        assert "درمان" in text or "مرخصی" in text or "ثبت‌نام" in text
