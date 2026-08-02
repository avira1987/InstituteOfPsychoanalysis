"""Fast unit tests for flow-through scripts (no DB)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.flow_through.build_matrix import build_matrix
from scripts.flow_through.build_sample_values import build_sample_values
from scripts.flow_through.resolve_ui_surface import enrich_matrix


def test_build_matrix_wave1_has_rows():
    report = build_matrix(wave=1)
    assert report["meta"]["process_count"] == 13
    assert report["meta"]["row_count"] >= 50
    codes = {r["process_code"] for r in report["rows"]}
    assert "fall_semester_preparation" in codes
    assert "start_therapy" in codes


def test_enrich_matrix_adds_ui_surface():
    report = build_matrix(wave=1, process_codes=["fall_semester_preparation"])
    enriched = enrich_matrix(report)
    row = enriched["rows"][0]
    assert "ui_layer" in row
    assert row.get("ui_surface_ok") is True


def test_build_sample_values_table_track():
    vals = build_sample_values(
        [
            {
                "name": "courses_fall",
                "type": "table",
                "columns": [
                    {"name": "course_name", "type": "text", "options_source": {"type": "course_catalog"}},
                    {"name": "track", "type": "text", "options_source": {"type": "course_committee_tracks"}},
                ],
            }
        ]
    )
    assert vals["courses_fall"][0]["track"] == "analytic_psychotherapy"
