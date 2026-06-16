"""تست اعتبارسنجی فرم داینامیک."""

import pytest

from app.services.dynamic_form_validation import merge_dynamic_into_context, validate_dynamic_answers


def test_validate_empty_ok():
    ok, missing = validate_dynamic_answers({"fields": []}, {})
    assert ok is True
    assert missing == []


def test_validate_required_text():
    schema = {
        "fields": [
            {"name": "a", "type": "text", "label_fa": "فیلد الف", "required": True},
        ]
    }
    assert validate_dynamic_answers(schema, {})[0] is False
    assert validate_dynamic_answers(schema, {"a": "x"})[0] is True


def test_show_if_hides_requirement():
    schema = {
        "fields": [
            {"name": "mode", "type": "radio_list", "label_fa": "حالت", "required": True},
            {
                "name": "extra",
                "type": "text",
                "label_fa": "اضافه",
                "required": True,
                "show_if": {"field": "mode", "equals": "full"},
            },
        ]
    }
    ok, _ = validate_dynamic_answers(schema, {"mode": "mini", "extra": ""})
    assert ok is True


def test_merge_context_namespaced():
    ctx = merge_dynamic_into_context({"x": 1}, "mykey", {"a": "b"})
    assert "__dynamic_form__mykey" in ctx
    assert ctx["__dynamic_form__mykey"]["a"] == "b"
