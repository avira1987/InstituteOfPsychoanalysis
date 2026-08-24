"""Tests for tuition installment plan computation."""

from app.services.tuition_installment_service import (
    apply_tuition_payment_context,
    compute_installment_plan,
    get_current_payable_from_plan,
    mark_installment_paid,
    split_installment_amounts,
)


def test_split_installment_amounts_remainder_on_last():
    assert split_installment_amounts(100, 3) == [33, 33, 34]


def test_installment_plan_equal_parts():
    plan = compute_installment_plan(1_200_000, "installment", 3, gap_days=25)
    assert len(plan) == 3
    assert sum(p["amount_rial"] for p in plan) == 1_200_000
    assert plan[0]["status"] == "pending"


def test_cash_payable_is_full_amount():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": 1_000_000,
            "payment_method": "cash",
        }
    )
    assert ctx["payable_amount_rial"] == 1_000_000
    assert ctx["payment_amount_rial"] == 1_000_000


def test_installment_payable_is_first_installment():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": 1_200_000,
            "payment_method": "installment",
            "installment_count": 3,
        }
    )
    assert ctx["payable_amount_rial"] == 400_000
    assert ctx["payment_amount_rial"] == 400_000
    assert ctx["current_installment_index"] == 1


def test_payable_before_method_uses_tuition_not_interview_fee():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": 15_000_000,
            "payment_amount_rial": 100_000,
        }
    )
    assert ctx["payable_amount_rial"] == 15_000_000
    assert ctx["interview_payment_amount_rial"] == 100_000
    assert ctx.get("payment_method_selected") is False


def test_installment_after_method_uses_first_installment():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": 15_000_000,
            "payment_amount_rial": 100_000,
            "payment_method": "installment",
            "installment_count": 3,
        }
    )
    assert ctx["payable_amount_rial"] == 5_000_000
    assert ctx.get("payment_method_selected") is True


def test_changing_installment_count_rebuilds_plan_and_payable():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": 15_000_000,
            "payment_method": "installment",
            "installment_count": 3,
        }
    )
    assert ctx["payable_amount_rial"] == 5_000_000
    assert len(ctx["installment_plan"]) == 3

    ctx["installment_count"] = 2
    ctx = apply_tuition_payment_context(ctx)
    assert len(ctx["installment_plan"]) == 2
    assert ctx["payable_amount_rial"] == 7_500_000


def test_mark_installment_paid_advances_payable():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": 1_200_000,
            "payment_method": "installment",
            "installment_count": 3,
        }
    )
    ctx = mark_installment_paid(ctx, "ref-1", 400_000)
    payable, idx = get_current_payable_from_plan(ctx["installment_plan"])
    assert payable == 400_000
    assert idx == 2
    assert ctx["pending_installments_remaining"] == 2


def test_cash_mark_paid_keeps_plan_settled():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": 700_000,
            "payment_method": "cash",
        }
    )
    assert ctx["installment_plan"][0]["status"] == "pending"
    ctx = mark_installment_paid(ctx, "cash-ref", 700_000)
    assert ctx["installment_plan"][0]["status"] == "paid"
    assert ctx["pending_installments_remaining"] == 0
    assert ctx.get("next_installment_due_at") is None


def test_installment_sms_still_owed_false_for_cash():
    from app.services.tuition_installment_service import installment_sms_still_owed

    assert installment_sms_still_owed({"payment_method": "cash", "pending_installments_remaining": 0}) is False
    assert installment_sms_still_owed(
        {
            "payment_method": "installment",
            "pending_installments_remaining": 2,
            "installment_plan": [{"status": "paid"}, {"status": "pending"}],
        }
    ) is True
    assert installment_sms_still_owed(
        {
            "payment_method": "installment",
            "pending_installments_remaining": 0,
            "installment_plan": [{"status": "paid"}],
        }
    ) is False
