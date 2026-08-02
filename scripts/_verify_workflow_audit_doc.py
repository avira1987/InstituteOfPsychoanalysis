"""Verify docs/workflow_interprocess_gap_audit.md covers all processes."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
index_codes = {
    p["code"]
    for p in json.loads((ROOT / "metadata/process_registry/INDEX.json").read_text(encoding="utf-8"))["processes"]
}
expected = index_codes | {"patient_referral"}
doc = (ROOT / "docs/workflow_interprocess_gap_audit.md").read_text(encoding="utf-8")
doc_codes = set(re.findall(r"^#### `([^`]+)`", doc, re.M))

missing = sorted(expected - doc_codes)
extra = sorted(doc_codes - expected)
sections = ["بخش ۰", "بخش ۱", "بخش ۲", "بخش ۳", "بخش ۴", "بخش ۵"]
missing_sections = [s for s in sections if s not in doc]

print(f"INDEX: {len(index_codes)} | doc blocks: {len(doc_codes)} | expected: {len(expected)}")
print(f"Missing: {missing}")
print(f"Extra: {extra}")
print(f"Missing sections: {missing_sections}")
assert not missing and not extra and not missing_sections, "Verification failed"
print("OK")
