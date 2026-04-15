"""Rule Evaluation Engine - Evaluates dynamic rules from metadata.

All rules are defined as JSON in the database. This engine interprets
and evaluates them at runtime without any hardcoded business logic.
"""

import math
import operator
from typing import Any, Optional
from datetime import datetime, timezone


# Operator mapping for rule expressions
OPERATORS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
    "starts_with": lambda a, b: str(a).startswith(str(b)),
    "ends_with": lambda a, b: str(a).endswith(str(b)),
    "is_null": lambda a, _: a is None,
    "is_not_null": lambda a, _: a is not None,
}


class RuleEvaluationError(Exception):
    """Raised when a rule cannot be evaluated."""
    def __init__(self, rule_code: str, message: str):
        self.rule_code = rule_code
        self.message = message
        super().__init__(f"Rule '{rule_code}': {message}")


def _is_plain_number(x: Any) -> bool:
    """True for int/float but not bool (bool is a subclass of int)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _coerce_none_for_ordering(field_value: Any, expected_value: Any) -> tuple[Any, Any]:
    """جلوگیری از TypeError در gt/gte/lt/lte وقتی یک طرف None و طرف دیگر عدد است (مثلاً debt_sessions_count)."""
    a, b = field_value, expected_value
    if a is None and _is_plain_number(b):
        a = 0
    elif b is None and _is_plain_number(a):
        b = 0
    elif a is None and b is None:
        a, b = 0, 0
    return a, b


class RuleResult:
    """Result of evaluating a single rule."""
    def __init__(self, rule_code: str, passed: bool, value: Any = None,
                 error_message: Optional[str] = None, details: Optional[dict] = None):
        self.rule_code = rule_code
        self.passed = passed
        self.value = value
        self.error_message = error_message
        self.details = details or {}

    def to_dict(self):
        return {
            "rule_code": self.rule_code,
            "passed": self.passed,
            "value": self.value,
            "error_message": self.error_message,
            "details": self.details,
        }


class RuleEvaluator:
    """
    Evaluates rules defined as JSON expressions.

    Supported expression types:
    - Simple comparison: {"field": "...", "operator": "...", "value": ...}
    - Logical AND: {"operator": "and", "conditions": [...]}
    - Logical OR: {"operator": "or", "conditions": [...]}
    - Logical NOT: {"operator": "not", "condition": {...}}
    - Conditional: {"if": {...}, "then": ..., "else": ...}
    - Formula: {"formula": "...", "reset_cycle": "..."}
    """

    def resolve_field(self, field_path: str, context: dict) -> Any:
        """Resolve a dotted field path from the context.

        Example: "student.is_intern" resolves context["student"]["is_intern"]
        """
        parts = field_path.split(".")
        current = context
        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    return None
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def evaluate_expression(self, expression: dict, context: dict) -> Any:
        """Evaluate a single expression against the context."""
        if not expression:
            return True

        op = expression.get("operator")

        # Logical AND
        if op == "and":
            conditions = expression.get("conditions", [])
            return all(self.evaluate_expression(c, context) for c in conditions)

        # Logical OR
        if op == "or":
            conditions = expression.get("conditions", [])
            return any(self.evaluate_expression(c, context) for c in conditions)

        # Logical NOT
        if op == "not":
            condition = expression.get("condition", {})
            return not self.evaluate_expression(condition, context)

        # Conditional (if/then/else)
        if "if" in expression:
            condition_result = self.evaluate_expression(expression["if"], context)
            if condition_result:
                return expression.get("then")
            else:
                return expression.get("else")

        # Formula evaluation
        if "formula" in expression:
            return self._evaluate_formula(expression["formula"], context)

        # Simple comparison
        if "field" in expression and op:
            field_value = self.resolve_field(expression["field"], context)
            expected_value = expression.get("value")
            # Resolve value when it references another context field (e.g. "instance.absence_quota")
            if isinstance(expected_value, str) and "." in expected_value and expected_value.startswith(("instance.", "student.", "payload.")):
                resolved = self.resolve_field(expected_value, context)
                if resolved is not None:
                    expected_value = resolved

            # Handle special operators
            if op in ("is_null", "is_not_null"):
                op_func = OPERATORS.get(op)
                return op_func(field_value, None)

            op_func = OPERATORS.get(op)
            if op_func is None:
                raise RuleEvaluationError("unknown", f"Unknown operator: {op}")

            if op in ("gt", "gte", "lt", "lte"):
                field_value, expected_value = _coerce_none_for_ordering(field_value, expected_value)

            return op_func(field_value, expected_value)

        return True

    def _evaluate_formula(self, formula: str, context: dict) -> Any:
        """Evaluate a mathematical formula with context variables.

        Supports: ceil, floor, round, min, max and basic arithmetic.
        """
        safe_namespace = {
            "ceil": math.ceil,
            "floor": math.floor,
            "round": round,
            "min": min,
            "max": max,
            "abs": abs,
        }

        # Flatten context for formula evaluation
        flat_context = self._flatten_context(context)
        safe_namespace.update(flat_context)

        try:
            result = eval(formula, {"__builtins__": {}}, safe_namespace)
            return result
        except Exception as e:
            raise RuleEvaluationError("formula", f"Formula evaluation failed: {e}")

    def _flatten_context(self, context: dict, prefix: str = "") -> dict:
        """Flatten nested context dict using dot notation for variable names."""
        result = {}
        for key, value in context.items():
            full_key = f"{prefix}.{key}" if prefix else key
            # Also create underscore version for formula compatibility
            underscore_key = full_key.replace(".", "_")
            if isinstance(value, dict):
                result.update(self._flatten_context(value, full_key))
            else:
                result[full_key] = value
                result[underscore_key] = value
        return result

    def evaluate_rule(self, rule: dict, context: dict) -> RuleResult:
        """Evaluate a complete rule definition against a context.

        Args:
            rule: Rule definition dict with code, expression, etc.
            context: Runtime context data (student info, instance data, etc.)

        Returns:
            RuleResult with pass/fail status and details.
        """
        rule_code = rule.get("code", "unknown")
        try:
            expression = rule.get("expression", {})
            result = self.evaluate_expression(expression, context)

            rule_type = rule.get("rule_type", "condition")

            if rule_type == "condition":
                return RuleResult(
                    rule_code=rule_code,
                    passed=bool(result),
                    value=result,
                )
            elif rule_type == "validation":
                passed = bool(result)
                error_msg = rule.get("error_message_fa") if not passed else None
                return RuleResult(
                    rule_code=rule_code,
                    passed=passed,
                    value=result,
                    error_message=error_msg,
                )
            elif rule_type == "computation":
                return RuleResult(
                    rule_code=rule_code,
                    passed=True,
                    value=result,
                )
            else:
                return RuleResult(
                    rule_code=rule_code,
                    passed=bool(result),
                    value=result,
                )

        except RuleEvaluationError:
            raise
        except Exception as e:
            return RuleResult(
                rule_code=rule_code,
                passed=False,
                error_message=f"Evaluation error: {str(e)}",
            )

    def evaluate_rules(self, rules: list[dict], context: dict) -> list[RuleResult]:
        """Evaluate multiple rules and return all results."""
        return [self.evaluate_rule(rule, context) for rule in rules]

    def all_passed(self, results: list[RuleResult]) -> bool:
        """Check if all rule results passed."""
        return all(r.passed for r in results)
