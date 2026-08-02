# وضعیت: آغاز درمان آموزشی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-08-02 |
| **منبع ورودی** | فلوچارت + متن ۷ گامی |

## پیاده‌سازی شیت وقت آزاد
- [x] مدل `EducationalTherapistSlot` + API + سرویس book/release
- [x] UI ادمین: `EducationalTherapistSlotsAdmin` (پنل پذیرش / هماهنگی درمان)
- [x] UI دانشجو: `therapist_slot_picker` + `StudentStartTherapyPanel`
- [x] اکشن `book_educational_therapist_slots` روی `therapist_selected`
- [x] آزادسازی واقعی اسلات روی `therapist_declined`

## نواقص
- [ ] قانون پذیرش مشروط (فرایند ثبت‌نام ترم ۲) — در فرایند دیگر
- [ ] ثبت غیبت خودکار در دوران مسدودی — در سرویس attendance

## قوانین اضافه‌شده
- already_started_therapy ✓
- therapy_not_started ✓
- schedule_valid_for_course ✓

## قالب‌های اعلان
- therapy_already_used ✓
- therapy_scheduled_student ✓
- therapy_scheduled_therapist ✓
