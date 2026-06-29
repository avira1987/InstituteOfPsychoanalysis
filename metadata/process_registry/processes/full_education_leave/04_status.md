# فرایند ۵۹ — مرخصی موقت از کل آموزش

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا | گسترش یافته — states/forms/transitions مطابق SOP |
| بک‌اند | `full_education_leave_service.py` + action handlers |
| UI دانشجو | `StudentFullEducationLeavePanel` |
| UI کمیته | `FullEducationLeaveCommitteeReviewPanel` |
| UI هماهنگی | `TherapistAssignmentReviewPanel` |

## یادداشت

- بازگشت از مرخصی از طریق فرایند ۶۰ (`return_to_full_education`) انجام می‌شود.
- رد درخواست بدون ارجاع خودکار به کمیته نظارت (مطابق SOP).
