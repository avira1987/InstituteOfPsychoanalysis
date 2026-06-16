"""فیلدهای محرمانهٔ نتیجهٔ مصاحبه نباید در پاسخ status/dashboard به دانشجو نشت کند."""

from types import SimpleNamespace

from app.api.process.routes import _redact_confidential_for_student


def _student():
    return SimpleNamespace(role="student")


def _operator(role="progress_committee"):
    return SimpleNamespace(role=role)


def test_student_status_strips_comprehensive_confidential_fields():
    status = {
        "process_code": "comprehensive_course_registration",
        "current_state": "result_rejected",
        "context_data": {
            "interview_evaluation_notes": "ضعف در ...",
            "interview_rejection_reason": "دلیل محرمانه",
            "interview_suggestion_text": "پیشنهاد دکتر مرادی",
            "allowed_course_count": 3,
            "some_public_field": "ok",
        },
    }
    out = _redact_confidential_for_student(status, _student())
    ctx = out["context_data"]
    assert "interview_evaluation_notes" not in ctx
    assert "interview_rejection_reason" not in ctx
    assert "interview_suggestion_text" not in ctx
    # فیلدهای غیرمحرمانه باید باقی بمانند
    assert ctx["allowed_course_count"] == 3
    assert ctx["some_public_field"] == "ok"


def test_student_status_strips_intro_interviewer_notes():
    status = {
        "process_code": "introductory_course_registration",
        "current_state": "interview_completed",
        "context_data": {
            "interviewer_notes": "یادداشت محرمانهٔ مصاحبه‌گر",
            "allowed_course_count": 1,
        },
    }
    out = _redact_confidential_for_student(status, _student())
    assert "interviewer_notes" not in out["context_data"]
    assert out["context_data"]["allowed_course_count"] == 1


def test_operator_status_keeps_confidential_fields():
    status = {
        "process_code": "comprehensive_course_registration",
        "current_state": "result_rejected",
        "context_data": {
            "interview_rejection_reason": "دلیل محرمانه",
            "interview_evaluation_notes": "ارزیابی",
        },
    }
    out = _redact_confidential_for_student(status, _operator())
    assert out["context_data"]["interview_rejection_reason"] == "دلیل محرمانه"
    assert out["context_data"]["interview_evaluation_notes"] == "ارزیابی"


def test_redaction_is_noop_without_confidential_keys():
    status = {
        "process_code": "comprehensive_course_registration",
        "current_state": "course_display",
        "context_data": {"allowed_course_count": 2},
    }
    out = _redact_confidential_for_student(status, _student())
    # بدون کلید محرمانه، همان شیء بازگردانده می‌شود (بدون کپی غیرضروری)
    assert out is status
