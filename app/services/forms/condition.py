"""ارزیابی شرط‌های مبتنی بر شیء (object predicates) برای فرم یکپارچه.

شکل گزاره:
    { "field": "payment_method", "op": "eq",  "value": "installment" }
    { "field": "interview_result", "op": "in", "value": ["x", "y"] }

عملگرها: eq | neq | in | nin | truthy | falsy | gt | lt | gte | lte | contains
سازگاری قدیمی: { "field": "...", "equals": ... }  ≡  op=eq
عبارت رشته‌ای metadata: visible_when / required_when (مثل "payment_method == 'installment'")
"""

from __future__ import annotations

import re
from typing import Any, Optional

_RE_EQ = re.compile(r"^\s*(\w+)\s*==\s*'([^']*)'\s*$")
_RE_NEQ = re.compile(r"^\s*(\w+)\s*!=\s*'([^']*)'\s*$")
_RE_IN = re.compile(r"^\s*(\w+)\s+in\s+\[(.*)\]\s*$")
_RE_NIN = re.compile(r"^\s*(\w+)\s+not\s+in\s+\[(.*)\]\s*$")
_RE_TRUTHY = re.compile(r"^\s*(\w+)\s*$")


def _parse_list(raw: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"'([^']*)'", raw)]


def expr_to_predicate(expr: Any) -> Optional[dict]:
    """عبارت رشته‌ای metadata را به گزارهٔ { field, op, value } تبدیل می‌کند."""
    if expr is None:
        return None
    if isinstance(expr, dict):
        return expr
    if not isinstance(expr, str):
        return None
    s = expr.strip()
    if not s:
        return None
    m = _RE_EQ.match(s)
    if m:
        return {"field": m.group(1), "op": "eq", "value": m.group(2)}
    m = _RE_NEQ.match(s)
    if m:
        return {"field": m.group(1), "op": "neq", "value": m.group(2)}
    m = _RE_IN.match(s)
    if m:
        return {"field": m.group(1), "op": "in", "value": _parse_list(m.group(2))}
    m = _RE_NIN.match(s)
    if m:
        return {"field": m.group(1), "op": "nin", "value": _parse_list(m.group(2))}
    m = _RE_TRUTHY.match(s)
    if m:
        return {"field": m.group(1), "op": "truthy"}
    return {"raw": s}


def _coerce_number(v: Any):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def evaluate_predicate(pred: Any, answers: dict) -> bool:
    """یک گزارهٔ شرطی را روی پاسخ‌های جاری ارزیابی می‌کند. نبودِ گزاره ⇒ True."""
    if not pred or not isinstance(pred, dict):
        return True
    if pred.get("raw"):
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


def _resolve_show_predicate(field: dict) -> Any:
    show_if = field.get("show_if")
    if show_if:
        return show_if
    vw = field.get("visible_when")
    if isinstance(vw, str):
        pred = expr_to_predicate(vw)
        if pred and "raw" not in pred:
            return pred
    return None


def _resolve_required_predicate(field: dict) -> Any:
    req_if = field.get("required_if")
    if isinstance(req_if, dict):
        return req_if
    if isinstance(req_if, str):
        pred = expr_to_predicate(req_if)
        if pred and "raw" not in pred:
            return pred
    rw = field.get("required_when")
    if isinstance(rw, str):
        pred = expr_to_predicate(rw)
        if pred and "raw" not in pred:
            return pred
    return None


def field_visible(field: dict, answers: dict) -> bool:
    """show_if / visible_when / visible_if کنترل نمایش فیلد را تعیین می‌کند."""
    show_pred = _resolve_show_predicate(field)
    if show_pred:
        return evaluate_predicate(show_pred, answers)
    visible_if = field.get("visible_if")
    if visible_if and isinstance(visible_if, dict):
        vals = answers or {}
        return all(vals.get(k) == v for k, v in visible_if.items())
    return True


def field_required(field: dict, answers: dict) -> bool:
    """required_if / required_when در صورت وجود اولویت دارد؛ وگرنه required ثابت."""
    req_pred = _resolve_required_predicate(field)
    if req_pred:
        return bool(field.get("required", True)) and evaluate_predicate(req_pred, answers)
    return bool(field.get("required"))
