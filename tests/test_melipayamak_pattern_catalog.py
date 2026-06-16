"""Tests for melipayamak_pattern_catalog and xlsx importer."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_importer():
    path = ROOT / "scripts" / "import_melipayamak_patterns_xlsx.py"
    spec = importlib.util.spec_from_file_location("import_melipayamak_patterns_xlsx", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_catalog_loads_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import melipayamak_pattern_catalog as mpc

    mpc.clear_pattern_catalog_cache()
    j = tmp_path / "p.json"
    j.write_text(
        json.dumps(
            {
                "source": "test",
                "patterns": [{"bodyId": 42, "title": "t", "templateText": "x"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MELIPAYAMAK_PATTERNS_JSON", str(j))
    mpc.clear_pattern_catalog_cache()
    cat = mpc.load_melipayamak_pattern_catalog()
    assert cat["count"] == 1
    assert mpc.get_pattern_by_body_id(42)["title"] == "t"


def test_import_xlsx_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    imx = _load_importer()

    monkeypatch.chdir(ROOT)
    xlsx = tmp_path / "patterns.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["کد متن", "عنوان", "متن"])
    ws.append([12345, "سلام", "کاربر %نام% کد {کد} را وارد کنید"])
    wb.save(xlsx)
    wb.close()

    data = imx.import_xlsx(xlsx)
    assert data["count"] == 1
    row = data["patterns"][0]
    assert row["bodyId"] == 12345
    assert row["title"] == "سلام"
    assert row["variablePlaceholders"] == ["نام", "کد"]


def test_placeholder_scan_preserves_left_to_right_order() -> None:
    imx = _load_importer()
    assert imx._extract_variables_ordered("بِ {1} نَ و {0}") == ["1", "0"]
    assert imx._extract_variables_ordered("{0}{1}{2}") == ["0", "1", "2"]
