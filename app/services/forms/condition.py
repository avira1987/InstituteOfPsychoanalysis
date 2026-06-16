"""ارزیابی شرط‌های مبتنی بر شیء (object predicates) برای فرم یکپارچه.

شکل گزاره:
    { "field": "payment_method", "op": "eq",  "value": "installment" }
    { "field": "interview_result", "op": "in", "value": ["x", "y"] }

عملگرها: eq | neq | in | nin | truthy | falsy | gt | lt | gte | lte | contains
سازگاری قدیمی: { "field": "...", "equals": ... }  ≡  op=eq
"""

from __future__ import annotations

from typing import Any


def _coerce_number(v: Any):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def evaluate_predicate(pred: Any, answers: dict) -> bool:
    """یک گزارهٔ شرطی را روی پاسخ‌های جاری ارزیابی می‌کند. نبودِ گزاره ⇒ True."""
    if not pred or not isinstance(pred, dict):
        return True
    field = pred.get("field")
    if not field:
        return True
    got = (answers or {}).get(field)

    # سازگاری قدیمی: equals
    if "equals" in pred and "op" not in pred:
        return got == pred.get("equals")

    op = (pred.get("op") or "eq").lower()
    want = pred.get("value")

    if op == "eq":
        return got == want
    if op == "neq":
        return got != want
    if op == "in":
        return got in want if isinstance(want, (list, tuple, set)) else False
    if op == "nin":
        return got not in want if isinstance(want, (list, tuple, set)) else True
    if op == "truthy":
        return bool(got)
    if op == "falsy":
        return not bool(got)
    if op == "contains":
        if isinstance(got, (list, tuple, set, str)):
            return want in got
        return False
    if op in ("gt", "lt", "gte", "lte"):
        a = _coerce_number(got)
        b = _coerce_number(want)
        if a is None or b is None:
            return False
        if op == "gt":
            return a > b
        if op == "lt":
            return a < b
        if op == "gte":
            return a >= b
        return a <= b
    return True


def field_visible(field: dict, answers: dict) -> bool:
    """show_if / visible_if کنترل نمایش فیلد را تعیین می‌کند."""
    show_if = field.get("show_if")
    if show_if:
        return evaluate_predicate(show_if, answers)
    visible_if = field.get("visible_if")
    if visible_if and isinstance(visible_if, dict):
        vals = answers or {}
        return all(vals.get(k) == v for k, v in visible_if.items())
    return True


def field_required(field: dict, answers: dict) -> bool:
    """required_if در صورت وجود اولویت دارد؛ وگرنه required ثابت."""
    req_if = field.get("required_if")
    if req_if and isinstance(req_if, dict):
        return bool(field.get("required", True)) and evaluate_predicate(req_if, answers)
    return bool(field.get("required"))
