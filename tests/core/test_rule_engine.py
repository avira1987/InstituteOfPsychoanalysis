"""Unit tests for the Rule Engine."""

import pytest
from app.core.rule_engine import RuleEvaluator, RuleResult, RuleEvaluationError


@pytest.fixture
def evaluator():
    return RuleEvaluator()


@pytest.fixture
def sample_context():
    return {
        "student": {
            "is_intern": False,
            "course_type": "comprehensive",
            "term_count": 3,
            "current_term": 3,
            "therapy_started": True,
            "weekly_sessions": 2,
        },
        "instance": {
            "leave_terms": 1,
            "current_week": 5,
            "absences_this_year": 2,
            "absence_quota": 6,
        },
    }


# ─── Simple Comparisons ────────────────────────────────────────

class TestSimpleComparisons:
    def test_eq_true(self, evaluator, sample_context):
        expr = {"field": "student.is_intern", "operator": "eq", "value": False}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_eq_false(self, evaluator, sample_context):
        expr = {"field": "student.is_intern", "operator": "eq", "value": True}
        assert evaluator.evaluate_expression(expr, sample_context) is False

    def test_gte(self, evaluator, sample_context):
        expr = {"field": "student.term_count", "operator": "gte", "value": 1}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_gt(self, evaluator, sample_context):
        expr = {"field": "student.term_count", "operator": "gt", "value": 2}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_lt(self, evaluator, sample_context):
        expr = {"field": "instance.current_week", "operator": "lt", "value": 9}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_lte(self, evaluator, sample_context):
        expr = {"field": "instance.leave_terms", "operator": "lte", "value": 1}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_ne(self, evaluator, sample_context):
        expr = {"field": "student.course_type", "operator": "ne", "value": "introductory"}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_in_operator(self, evaluator, sample_context):
        expr = {"field": "student.course_type", "operator": "in", "value": ["comprehensive", "introductory"]}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_not_in_operator(self, evaluator, sample_context):
        expr = {"field": "student.course_type", "operator": "not_in", "value": ["other"]}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_is_null(self, evaluator, sample_context):
        expr = {"field": "student.nonexistent", "operator": "is_null", "value": None}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_is_not_null(self, evaluator, sample_context):
        expr = {"field": "student.course_type", "operator": "is_not_null", "value": None}
        assert evaluator.evaluate_expression(expr, sample_context) is True


# ─── Logical Operators ──────────────────────────────────────────

class TestLogicalOperators:
    def test_and_all_true(self, evaluator, sample_context):
        expr = {
            "operator": "and",
            "conditions": [
                {"field": "student.term_count", "operator": "gte", "value": 1},
                {"field": "student.is_intern", "operator": "eq", "value": False},
            ],
        }
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_and_one_false(self, evaluator, sample_context):
        expr = {
            "operator": "and",
            "conditions": [
                {"field": "student.term_count", "operator": "gte", "value": 1},
                {"field": "student.is_intern", "operator": "eq", "value": True},
            ],
        }
        assert evaluator.evaluate_expression(expr, sample_context) is False

    def test_or_one_true(self, evaluator, sample_context):
        expr = {
            "operator": "or",
            "conditions": [
                {"field": "student.is_intern", "operator": "eq", "value": True},
                {"field": "student.term_count", "operator": "gte", "value": 1},
            ],
        }
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_or_all_false(self, evaluator, sample_context):
        expr = {
            "operator": "or",
            "conditions": [
                {"field": "student.is_intern", "operator": "eq", "value": True},
                {"field": "student.term_count", "operator": "lt", "value": 1},
            ],
        }
        assert evaluator.evaluate_expression(expr, sample_context) is False

    def test_not(self, evaluator, sample_context):
        expr = {
            "operator": "not",
            "condition": {"field": "student.is_intern", "operator": "eq", "value": True},
        }
        assert evaluator.evaluate_expression(expr, sample_context) is True


# ─── Conditional (if/then/else) ─────────────────────────────────

class TestConditional:
    def test_if_true(self, evaluator, sample_context):
        expr = {
            "if": {"field": "student.therapy_started", "operator": "eq", "value": True},
            "then": "already_started",
            "else": "not_started",
        }
        result = evaluator.evaluate_expression(expr, sample_context)
        assert result == "already_started"

    def test_if_false(self, evaluator, sample_context):
        expr = {
            "if": {"field": "student.is_intern", "operator": "eq", "value": True},
            "then": "intern_path",
            "else": "regular_path",
        }
        result = evaluator.evaluate_expression(expr, sample_context)
        assert result == "regular_path"


# ─── Formula ───────────────────────────────────────────────────

class TestFormula:
    def test_formula_ceil(self, evaluator, sample_context):
        expr = {"formula": "ceil(student_weekly_sessions * 3)"}
        result = evaluator.evaluate_expression(expr, sample_context)
        assert result == 6  # ceil(2 * 3) = 6

    def test_formula_with_arithmetic(self, evaluator, sample_context):
        expr = {"formula": "student_term_count * 10 + 5"}
        result = evaluator.evaluate_expression(expr, sample_context)
        assert result == 35  # 3 * 10 + 5

    def test_formula_error(self, evaluator, sample_context):
        expr = {"formula": "undefined_var * 2"}
        with pytest.raises(RuleEvaluationError):
            evaluator.evaluate_expression(expr, sample_context)


# ─── Rule Evaluation ───────────────────────────────────────────

class TestRuleEvaluation:
    def test_condition_rule_pass(self, evaluator, sample_context):
        rule = {
            "code": "is_not_intern",
            "name_fa": "غیر انترن",
            "rule_type": "condition",
            "expression": {"field": "student.is_intern", "operator": "eq", "value": False},
        }
        result = evaluator.evaluate_rule(rule, sample_context)
        assert result.passed is True
        assert result.rule_code == "is_not_intern"

    def test_condition_rule_fail(self, evaluator, sample_context):
        rule = {
            "code": "is_intern",
            "rule_type": "condition",
            "expression": {"field": "student.is_intern", "operator": "eq", "value": True},
        }
        result = evaluator.evaluate_rule(rule, sample_context)
        assert result.passed is False

    def test_validation_rule_pass(self, evaluator, sample_context):
        rule = {
            "code": "min_term",
            "rule_type": "validation",
            "expression": {"field": "student.term_count", "operator": "gte", "value": 1},
            "error_message_fa": "حداقل ترم لازم",
        }
        result = evaluator.evaluate_rule(rule, sample_context)
        assert result.passed is True
        assert result.error_message is None

    def test_validation_rule_fail(self, evaluator, sample_context):
        rule = {
            "code": "min_term",
            "rule_type": "validation",
            "expression": {"field": "student.term_count", "operator": "gte", "value": 10},
            "error_message_fa": "حداقل ۱۰ ترم لازم است",
        }
        result = evaluator.evaluate_rule(rule, sample_context)
        assert result.passed is False
        assert result.error_message == "حداقل ۱۰ ترم لازم است"

    def test_computation_rule(self, evaluator, sample_context):
        rule = {
            "code": "absence_quota",
            "rule_type": "computation",
            "expression": {"formula": "ceil(student_weekly_sessions * 3)"},
        }
        result = evaluator.evaluate_rule(rule, sample_context)
        assert result.passed is True
        assert result.value == 6

    def test_evaluate_multiple_rules(self, evaluator, sample_context):
        rules = [
            {"code": "r1", "rule_type": "condition", "expression": {"field": "student.is_intern", "operator": "eq", "value": False}},
            {"code": "r2", "rule_type": "condition", "expression": {"field": "student.term_count", "operator": "gte", "value": 1}},
        ]
        results = evaluator.evaluate_rules(rules, sample_context)
        assert len(results) == 2
        assert evaluator.all_passed(results) is True

    def test_evaluate_multiple_rules_one_fails(self, evaluator, sample_context):
        rules = [
            {"code": "r1", "rule_type": "condition", "expression": {"field": "student.is_intern", "operator": "eq", "value": True}},
            {"code": "r2", "rule_type": "condition", "expression": {"field": "student.term_count", "operator": "gte", "value": 1}},
        ]
        results = evaluator.evaluate_rules(rules, sample_context)
        assert evaluator.all_passed(results) is False


# ─── Edge Cases ────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_expression(self, evaluator, sample_context):
        assert evaluator.evaluate_expression({}, sample_context) is True

    def test_missing_field(self, evaluator, sample_context):
        expr = {"field": "nonexistent.field", "operator": "eq", "value": None}
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_nested_and_or(self, evaluator, sample_context):
        expr = {
            "operator": "and",
            "conditions": [
                {
                    "operator": "or",
                    "conditions": [
                        {"field": "student.course_type", "operator": "eq", "value": "comprehensive"},
                        {"field": "student.course_type", "operator": "eq", "value": "introductory"},
                    ],
                },
                {"field": "student.term_count", "operator": "gte", "value": 1},
            ],
        }
        assert evaluator.evaluate_expression(expr, sample_context) is True

    def test_week9_rule(self, evaluator):
        """Test the week 9 deadline rule from SOP."""
        context = {
            "student": {"course_type": "comprehensive", "therapy_started": False},
            "instance": {"current_week": 10},
        }
        expr = {
            "operator": "and",
            "conditions": [
                {"field": "student.course_type", "operator": "eq", "value": "comprehensive"},
                {"field": "student.therapy_started", "operator": "eq", "value": False},
                {"field": "instance.current_week", "operator": "gt", "value": 9},
            ],
        }
        assert evaluator.evaluate_expression(expr, context) is True

    def test_week9_rule_not_triggered(self, evaluator):
        """Week 9 rule should NOT trigger if therapy already started."""
        context = {
            "student": {"course_type": "comprehensive", "therapy_started": True},
            "instance": {"current_week": 10},
        }
        expr = {
            "operator": "and",
            "conditions": [
                {"field": "student.course_type", "operator": "eq", "value": "comprehensive"},
                {"field": "student.therapy_started", "operator": "eq", "value": False},
                {"field": "instance.current_week", "operator": "gt", "value": 9},
            ],
        }
        assert evaluator.evaluate_expression(expr, context) is False
