"""سیاست فعال/غیرفعال بودن پرداخت قسطی."""

from app.services.installment_settings_service import (
    apply_installment_policy_to_forms,
    installment_new_selection_blocked,
    is_installment_enabled,
)


def test_missing_flag_defaults_enabled():
    assert is_installment_enabled(None) is True
    assert is_installment_enabled({}) is True
    assert is_installment_enabled({"term2_installment_gap_days": 25}) is True


def test_explicit_disabled():
    assert is_installment_enabled({"installment_enabled": False}) is False
    assert is_installment_enabled({"installment_enabled": "false"}) is False


def test_new_selection_blocked_when_disabled():
    policy = {"installment_enabled": False}
    assert installment_new_selection_blocked(policy, {"payment_method": "installment"}, {}) is True
    assert installment_new_selection_blocked(policy, {"payment_method": "cash"}, {}) is False


def test_existing_installment_is_grandfathered():
    policy = {"installment_enabled": False}
    ctx = {"payment_method": "installment"}
    assert installment_new_selection_blocked(policy, {"payment_method": "installment"}, ctx) is False


def test_forms_hide_installment_option_when_disabled():
    forms = [
        {
            "code": "pay",
            "fields": [
                {
                    "name": "payment_method",
                    "options": [
                        {"value": "cash", "label_fa": "نقدی"},
                        {"value": "installment", "label_fa": "اقساط"},
                    ],
                },
                {"name": "installment_count", "options": [2, 3, 4]},
            ],
        }
    ]
    out = apply_installment_policy_to_forms(forms, {"installment_enabled": False})
    names = [f["name"] for f in out[0]["fields"]]
    assert names == ["payment_method"]
    values = [o["value"] for o in out[0]["fields"][0]["options"]]
    assert values == ["cash"]
    assert forms[0]["fields"][0]["options"][1]["value"] == "installment"


def test_forms_keep_installment_when_already_selected():
    forms = [
        {
            "fields": [
                {
                    "name": "payment_method",
                    "options": [{"value": "cash"}, {"value": "installment"}],
                },
                {"name": "installment_count"},
            ]
        }
    ]
    out = apply_installment_policy_to_forms(
        forms,
        {"installment_enabled": False},
        already_on_installment=True,
    )
    names = [f["name"] for f in out[0]["fields"]]
    assert "installment_count" in names
    values = [o["value"] for o in out[0]["fields"][0]["options"]]
    assert "installment" in values
