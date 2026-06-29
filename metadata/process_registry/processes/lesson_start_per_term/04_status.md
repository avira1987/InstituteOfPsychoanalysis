# وضعیت: آغاز هر درس در هر ترم

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-06-28 |
| **منبع ورودی** | SOP مرحلهٔ ۴۱ |
| **sop_order** | 41 |

## نقش‌ها
- student (دانشجو — ثبت‌نام در درس)
- instructor (مدرس — ثبت حضور در class_attendance)
- teaching_assistant
- course_committee_executive
- system

## UI دانشجو
- [x] `StudentLessonStartPerTermPanel` — stepper، راهنمای وضعیت، لینک آنلاین، جدول جلسات
- [x] `lessonStartPerTermDisplay.jsx` — برچسب‌ها و resolver context
- [x] اتصال در `StudentPortal.jsx`
- [x] بهبود `StudentCourseStatusPanel` — لینک آنلاین و جلسات حضور در تب یادگیری

## UI مدرس
- [x] `InstructorLessonAttendancePanel` — ثبت حضور جلسه‌ای (فرایند class_attendance)
- [x] `instructor_course_roster_service.py` + `GET /panel/instructor/course-roster`
- [x] اتصال در `StaffPortal.jsx` (lane instruction)

## نواقص
- [ ] اتصال LMS واقعی برای لینک کلاس
- [ ] داشبورد lane آموزش: ویجت دروس + تعداد class_attendance منتظر
- [ ] CTA دستی «ثبت درس این ترم» در داشبورد دانشجو

## یادداشت
زنجیره سیستمی پس از `enrolled`: links_created → attendance_list_ready → lesson_active (`lesson_start_chaining.py`).
همگام‌سازی SOP: `scripts/sync_sop_doc_from_registry_files.py --code lesson_start_per_term`
