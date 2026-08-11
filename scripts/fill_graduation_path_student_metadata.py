"""One-off helper: fill student_short/task/why on graduation-path process metadata."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "metadata" / "processes"

SHORT_OVERRIDES: dict[str, dict[str, str]] = {}
TASKS: dict[str, dict[str, str]] = {
    "theory_course_completion": {
        "awaiting_session_18": "درس شما در انتظار جلسه ۱۸ است. پس از برگزاری جلسه، مدرس مشارکت را ثبت می‌کند.",
        "session_18_entry": "جلسه ۱۸ — مدرس در حال ثبت مشارکت و انتخاب پک آزمون است.",
        "final_exam_open": "آزمون تستی آنلاین (۸۲ نمره) آماده است. غیبت در آزمون → Incomplete.",
        "grades_computed": "نمرات در حال نهایی‌سازی است.",
        "borderline_student_choice": "نمره شما در بازه مرزی (۶۴ تا ۷۳) است. می‌توانید امتحان مجدد (با پرداخت) یا دوباره گذراندن درس را انتخاب کنید.",
        "retake_exam_open": "امتحان مجدد فعال شد. پس از پرداخت، در زمان مقرر آزمون را بگذرانید.",
        "qualitative_eval_pending": "مدرس فرم ارزیابی کیفی را تکمیل می‌کند.",
        "grades_locked": "نمره نهایی ثبت و قفل شد.",
        "session_18_delay": "مهلت ثبت جلسه ۱۸ گذشته است. با دفتر آموزش تماس بگیرید.",
        "qualitative_eval_delay": "تأخیر در ارزیابی کیفی. با دفتر آموزش تماس بگیرید.",
    },
    "skills_course_completion": {
        "awaiting_session_17": "درس شما در انتظار جلسه ۱۷ است. پس از برگزاری امتحان عملی، مدرس نمرات را ثبت می‌کند.",
        "session_17_grades_entry": "جلسه ۱۷ — مدرس در حال ثبت مشارکت و امتحان عملی است.",
        "awaiting_session_18": "نمرات جلسه ۱۷ ثبت شد. جلسه ۱۸ (آزمون تستی) در راه است.",
        "session_18_grades_entry": "جلسه ۱۸ — آزمون تستی برگزار می‌شود. غیبت در عملی یا تست → Incomplete.",
        "grades_computed": "نمرات در حال نهایی‌سازی است.",
        "ta_evaluation_entry": "مدرس در حال ارزیابی کمک‌مدرس است.",
        "qualitative_eval_pending": "مدرس فرم ارزیابی کیفی را تکمیل می‌کند.",
        "grades_locked": "نمره نهایی ثبت و قفل شد.",
        "session_17_delay": "مهلت ثبت جلسه ۱۷ گذشته است. با دفتر آموزش تماس بگیرید.",
        "qualitative_eval_delay": "تأخیر در ارزیابی کیفی. با دفتر آموزش تماس بگیرید.",
    },
    "film_observation_course_completion": {
        "grades_entry": "گزارش پایانی درس را فقط به‌صورت PDF آپلود کنید. فرم از پایان جلسه ۱۷ باز و در ۲۴:۰۰ روز جلسه ۱۸ بسته می‌شود.",
        "grades_locked": "نمره گزارش ثبت شد. اگر نمره نهایی شما در بازه مرزی ۶۴ تا ۷۳ باشد، می‌توانید امتحان مجدد یا دوباره گذراندن درس را انتخاب کنید.",
        "delay_reported": "مهلت ثبت یا تصحیح گزارش گذشته است. برای پیگیری با دفتر آموزش تماس بگیرید.",
    },
    "live_therapy_observation_course_completion": {
        "grades_entry": "گزارش پایانی درس را فقط به‌صورت PDF آپلود کنید. فرم از پایان جلسه ۱۷ باز و در ۲۴:۰۰ روز جلسه ۱۸ بسته می‌شود.",
        "grades_locked": "نمره گزارش ثبت شد. اگر نمره نهایی شما در بازه مرزی ۶۴ تا ۷۳ باشد، می‌توانید امتحان مجدد یا دوباره گذراندن درس را انتخاب کنید.",
        "delay_reported": "مهلت ثبت یا تصحیح گزارش گذشته است. برای پیگیری با دفتر آموزش تماس بگیرید.",
    },
    "live_supervision_course_completion": {
        "sessions_in_progress": "کلاس سوپرویژن زنده برای شما فعال است. پس از هر جلسه پشت‌آینه، فرم پیاده‌سازی در پورتال شما باز می‌شود.",
        "mirror_implementation_pending": "لطفاً جلسه پشت آینه خود را پیاده‌سازی کنید. مهلت: ۵ روز پس از برگزاری جلسه.",
        "mirror_eval_pending": "مدرس در حال تکمیل ارزیابی ۳ جلسه پشت‌آینه است.",
        "final_eval_pending": "هجدهمین حضور شما ثبت شد. مدرس موظف است ارزیابی نهایی را تا پایان امروز تکمیل کند.",
        "completed": "درس سوپرویژن زنده برای شما تکمیل شد و در کارنامه ثبت می‌گردد.",
        "mirror_write_violation": "مهلت پیاده‌سازی پشت‌آینه گذشته است. گزارش به کمیته نظارت ارسال شده؛ هرچه سریع‌تر تکلیف را ثبت کنید.",
        "mirror_eval_violation": "تأخیر در ارزیابی پشت‌آینه گزارش شده؛ با دفتر آموزش تماس بگیرید.",
        "final_eval_delay": "تأخیر در ارزیابی نهایی گزارش شده؛ با دفتر آموزش تماس بگیرید.",
    },
    "thesis_defense_request": {
        "eligibility_check": "وضعیت چهار شرط را بررسی کنید. در صورت احراز همهٔ شروط، فایل PDF گزارش ۱۵۰ ساعت بیماران سایکوتیک را بارگذاری و «ادامه و ثبت مرحله» را بزنید.",
        "conditions_not_met": "شرایط دفاع هنوز کامل نیست؛ جزئیات در همین صفحه نمایش داده می‌شود.",
        "progress_committee_review": "گزارش شما در کمیته پیشرفت در حال بررسی است. پس از اعلام نتیجه، این صفحه به‌روز می‌شود.",
        "report_rejected": "کمیته پیشرفت گزارش را رد کرده است؛ با کمیته پیشرفت تماس بگیرید.",
        "report_revision": "کمیته پیشرفت نیاز به اصلاح گزارش سایکوتیک اعلام کرده است؛ فایل اصلاح‌شده را بارگذاری کنید.",
        "supervision_committee_review": "پرونده در کمیته نظارت است. پس از صدور مجوز یا رد، وضعیت اینجا نمایش داده می‌شود.",
        "defense_permit_denied": "کمیته نظارت مجوز دفاع صادر نکرده است. توضیحات در باکس زیر آمده است.",
        "thesis_upload": "مجوز دفاع صادر شد. فایل پایان‌نامه / گزارش موردی (PDF) را بارگذاری کنید.",
        "education_committee_scheduling": "پایان‌نامه ثبت شد. کمیته آموزش در حال تعیین زمان و داوران است.",
        "first_defense_held": "زمان دفاع ثبت شده است. در روز مقرر طبق اعلام کمیته حاضر شوید.",
        "revision_required": "حداقل یک داور نمره C/D/F داده است. حداکثر ۲ هفته فرصت دارید فایل اصلاح‌شده را بارگذاری کنید.",
        "revision_upload": "فایل پایان‌نامه اصلاح‌شده را بارگذاری کنید؛ پس از ثبت، منتظر زمان‌بندی دفاع مجدد باشید.",
        "revision_delay_violation": "مهلت بارگذاری اصلاحات گذشته است؛ گزارش تخلف ثبت شده است.",
        "second_defense_held": "دفاع مجدد برنامه‌ریزی شده است. در روز مقرر حاضر شوید.",
        "defense_passed": "تبریک — دفاع با موفقیت (PASS) به پایان رسید.",
        "defense_failed": "نتیجه نهایی دفاع: مردود (FAIL). در صورت پرسش با کمیته پیشرفت تماس بگیرید.",
    },
    "upgrade_to_educational_therapist": {
        "student_start": "شرایط ارتقا را مطالعه کنید و درخواست را ثبت کنید.",
        "eligibility_failed": "دانشجوی گرامی، شما شرایط لازم جهت ارتقا به درمانگر آموزشی را کسب نکرده‌اید.",
        "monitoring_review": "پرونده در کمیته نظارت در حال بررسی است.",
        "monitoring_rejected": "صلاحیت شما توسط کمیته نظارت تأیید نشد. برای پیگیری با بخش آموزش تماس بگیرید.",
        "interview_scheduling": "کمیته درمان آموزشی در حال تنظیم وقت مصاحبه است.",
        "interview_held": "مصاحبه برگزار می‌شود یا در حال برگزاری است.",
        "interview_rejected": "صلاحیت شما پس از مصاحبه تأیید نشد. برای پیگیری با کمیته درمان آموزشی تماس بگیرید.",
        "therapy_readiness_check": "سامانه در حال بررسی وضعیت درمان شخصی شماست.",
        "therapy_frequency_adjustment": "درمان شخصی را به حداقل یک جلسه در هفته افزایش دهید. مهلت: ۱۰ روز.",
        "therapy_frequency_escalation": "مهلت افزایش فرکانس درمان در حال پیگیری است؛ درمان هفتگی را فعال کنید.",
        "personal_therapy_hours": "۵۰ ساعت دیگر درمان شخصی را دریافت کنید؛ قوانین سختگیرانه غیبت/کنسلی اعمال نمی‌شود.",
        "therapist_selection": "از شیت وقت‌های آزاد درمانگران، درمانگر پیشنهادی خود را انتخاب کنید.",
        "therapist_committee_review": "درمانگر پیشنهادی در حال بررسی توسط کمیته است.",
        "supervision_readiness_check": "سامانه در حال بررسی وضعیت سوپرویژن فردی شماست.",
        "supervision_frequency_adjustment": "سوپرویژن فردی را به دو جلسه در ماه افزایش دهید.",
        "supervision_restart": "سوپرویژن قبلی قطع شده؛ با عضو هیئت علمی کامل سوپرویژن را آغاز کنید.",
        "supervision_hours": "تا تکمیل ۵۰ ساعت سوپرویژن فردی ادامه دهید.",
        "supervisor_selection": "از شیت وقت‌های آزاد سوپروایزرها (هیئت علمی کامل) زمان انتخاب کنید.",
        "et_availability_slots": "دو زمان خالی برای ارائه خدمات به‌عنوان درمانگر آموزشی ثبت کنید.",
        "promotion_completed": "ارتقا به درمانگر آموزشی با موفقیت تکمیل شد.",
    },
}


def short_label(state: dict) -> str:
    code = state["code"]
    name = state.get("name_fa") or code
    if len(name) > 48:
        return name.split("—")[0].strip() or name[:48]
    return name


def enrich(process_code: str) -> None:
    path = BASE / f"{process_code}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = TASKS.get(process_code, {})
    for state in data.get("states", []):
        code = state["code"]
        task = tasks.get(code)
        if not task:
            continue
        meta = state.setdefault("metadata", {})
        meta.setdefault("student_short_fa", short_label(state))
        meta.setdefault("student_task_fa", task)
        meta.setdefault("student_why_fa", task)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"updated {process_code}")


if __name__ == "__main__":
    for code in TASKS:
        enrich(code)
