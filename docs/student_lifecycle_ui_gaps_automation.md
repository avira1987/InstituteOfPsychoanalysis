# کمبودهای UI مسیر تحصیلی دانشجو — چک‌لیست اتوماسیون

**نسخه:** 1.0  
**تاریخ:** 2026-06-21  
**مرجع ممیزی:** `reports/customer_acceptance_audit.md` (Readiness: **100%**)  
**مرجع مسیر:** `app/meta/student_lifecycle_matrix.py` + سند مسیر دانشجو

---

## نحوهٔ استفاده

هر **گام** یک کار قابل تحویل است. وضعیت را علامت بزنید:

| نماد | معنی |
|------|------|
| ✅ | UI کامل — دانشجو/اپراتور می‌تواند در وب تمام کند |
| 🟡 | UI جزئی — مسیر workaround یا ناقص |
| 🔴 | UI ناقص — باید ساخته/تکمیل شود |
| ⚪ | سیستمی — UI دانشجو لازم نیست (scheduler/backend) |
| 👤 | نقش دیگر — UI در پنل مدرس/درمانگر/کمیته |

**فایل‌های UI مشترک (الگوی فعلی):**

- دانشجو: `admin-ui/src/pages/StudentPortal.jsx` + `StudentQuestCard.jsx` + `ProcessStepForms.jsx` + `SepPaymentPanel.jsx` + `InterviewSlotPicker.jsx`
- مصاحبه‌گر: `InterviewerPortal.jsx` + `InterviewerResultPanel.jsx`
- کارمند/پذیرش: `StaffPortal.jsx`
- کمیته: `CommitteePortal.jsx`
- درمانگر/سوپروایزر: `TherapistPortal.jsx` / `SupervisorPortal.jsx`
- آماده‌سازی ترم: `SemesterPrepPage.jsx` و صفحات فرعی

---

## خلاصهٔ وضعیت (مسیر اصلی)

| فاز | فرایندهای کلیدی | UI دانشجو | اولویت تکمیل |
|-----|------------------|-----------|--------------|
| P0 ورود | ثبت‌نام آشنایی/جامع | ✅ | بالا (مصاحبه‌گر) |
| P1 آشنایی | ترم، پایان ترم، ترم ۲ | 🟡 | متوسط (کارنامه) |
| P2 جامع | ثبت‌نام ترم، پایان ترم | 🟡 | متوسط (ارزیابی استاد) |
| P3 درمان | آغاز، پرداخت، خاتمه | ✅ | پایین |
| P4 سوپرویژن | بلوک ۵۰h، انتقال | ✅ | پایین |
| P8 پایان | دروس، مقاله، دفاع | 🟡 | بالا (مقاله/درس) |
| P7 کارورزی | آمادگی انترn | 🟡 | متوسط (سفته حضوری) |

**جمع‌بندی:** اکثر **اقدامات تکراری دانشجو** (ثبت‌نام، پرداخت، درمان، سوپرویژن) از `StudentQuestCard` پشتیبانی می‌شوند. **شکاف‌های اصلی:** (۱) مصاحبه‌گر، (۲) دانلود کارنامه/گواهی، (۳) ارزیابی استاد، (۴) خاتمه دروس و مقاله‌نویسی، (۵) شروع خودکار برخی فرایندها.

---

## فاز ۰ — ورود و ثبت‌نام اولیه

### گام ۰.۱ — `introductory_course_registration` (ثبت‌نام دوره آشنایی)

- [x] **وضعیت کلی:** ✅ — audit: `user_can_complete: YES`

| کار | UI موجود؟ | جزئیات |
|-----|-----------|--------|
| فرم پذیرش | ✅ | `StudentRegistration` / مسیر عمومی |
| انتخاب وقت مصاحبه | ✅ | `InterviewSlotPicker` در `StudentQuestCard` |
| پرداخت مصاحبه | ✅ | `SepPaymentPanel` |
| آپلود مدارک | ✅ | `ProcessStepForms` + `StudentProfileDocumentsSection` |
| انتخاب درس + پرداخت شهریه | ✅ | `StudentQuestCard` + `SepPaymentPanel` |
| **ثبت نتیجه مصاحبه (مصاحبه‌گر)** | ✅ | `InterviewerResultPanel` در `InterviewerPortal` |

**کار تکمیل (گام ۰.۱-الف):** فرم ترنزیشن نتیجه مصاحبه در `InterviewerPortal.jsx` (الگو: `StaffPortal` pending + `ProcessStepForms`).

**فایل‌ها:** `admin-ui/src/pages/InterviewerPortal.jsx`, `metadata/customer_acceptance_alternate_paths.json` → `partial_ui_paths.introductory_course_registration`

**معیار پذیرش:** مصاحبه‌گر بدون ورود به staff بتواند نتیجه را ثبت کند و فرایند دانشجو جلو برود.

---

### گام ۰.۲ — `comprehensive_course_registration` (ثبت‌نام دوره جامع)

- [x] **وضعیت کلی:** ✅ — audit: `user_can_complete: YES`

| کار | UI موجود؟ | جزئیات |
|-----|-----------|--------|
| درخواست + گزارش تجربه | ✅ | `StudentQuestCard` / فرم مرحله |
| مصاحبه + پرداخت | ✅ | مشابه آشنایی |
| پرداخت دروس ترم ۳ | ✅ | `SepPaymentPanel` |
| ثبت نتیجه مصاحبه | ✅ | همان پنل مصاحبه‌گر |
| **شروع خودکار برای واجد شرایط** | ✅ | `operator_gap_rules.json` → `enabled: true` + کارت `showManualRegStart` |

**کار تکمیل (گام ۰.۲-الف):** همان UI مصاحبه‌گر (گام ۰.۱-الف).

**کار تکمیل (گام ۰.۲-ب):** فعال‌سازی rule + نمایش کارت «شروع ثبت‌نام جامع» در داشبورد وقتی ۱۰ درس پاس شده (`StudentPortal` + `operator_gap_engine`).

**فایل‌ها:** `metadata/operator_gap_rules.json`, `app/services/operator_gap_engine.py`, `admin-ui/src/pages/StudentPortal.jsx`

---

### گام ۰.۳ — `fall_semester_preparation` / `winter_semester_preparation`

- [x] **وضعیت کلی:** ✅ برای اپراتور — ✅ نمایش تقویم برای دانشجو (read-only)

| کار | UI موجود؟ |
|-----|-----------|
| workbench همه مراحل | ✅ `SemesterPrepWorkbenchPage.jsx` |
| تقویم پاییز (redirect) | ✅ → workbench |
| بازبینی لیست دروس زمستان (redirect) | ✅ → workbench |
| هاب آماده‌سازی | ✅ `SemesterPrepPage.jsx` |
| تقویم آموزشی دانشجو | ✅ `StudentAcademicCalendarPanel.jsx` |

**کار دانشجو:** مشاهده تقویم و مهلت ثبت‌نام — بدون اقدام در فرایند آماده‌سازی.

---

## فاز ۱ — ترم‌های آشنایی

### گام ۱.۱ — `lesson_start_per_term` (شروع درس هر ترم)

- [ ] **وضعیت:** ✅ — `form_alternate_paths` → `StudentQuestCard` + `ProcessStepForms`

**Scheduler:** `process_scheduler.py` → `term_start_lesson` — خودکار پس از `term_start_date`.

**کار اختیاری:** دکمهٔ دستی «ثبت درس» اگر scheduler عقب افتاد (کارت در داشبورد).

---

### گام ۱.۲ — `class_attendance` (حضور کلاس)

- [x] **وضعیت:** 👤 + 🟡 — audit: `user_can_complete: NO` (مدرس ثبت می‌کند)

| نقش | UI |
|-----|-----|
| مدرس | پنل مدرس — لیست حضور |
| دانشجو | 🟡 **ویجت N از ۵ در `StudentCourseStatusPanel`** |

**کار تکمیل (گام ۱.۲-الف):** ویجت در `StudentPortal` → تب یادگیری: «وضعیت حضور درس X — N از ۵ غیبت».

**فایل‌ها:** `StudentPortal.jsx`, API وضعیت از `extra_data.lms` یا endpoint جدید.

---

### گام ۱.۳ — `introductory_term_end` (پایان ترم آشنایی)

- [x] **وضعیت:** ⚪ + ✅ برای **نمایش خروجی**

| کار | UI |
|-----|-----|
| تولید کارنامه (سیستم) | ✅ backend — `generate_term_transcript` |
| **دانلود PDF کارنامه ترمی/تجمیعی** | ✅ **`StudentTranscriptsPanel` در پروفایل** |
| پیامک مهلت ثبت‌نام | ✅ SMS |
| مسدودیت درمان (مشروط) | ⚪ popup از فرایند بعد |

**کار تکمیل (گام ۱.۳-الف):** بخش «کارنامه‌ها» در پنل دانشجو — لینک دانلود از `context_data` یا `document_service`.

**فایل‌ها:** `admin-ui/src/pages/StudentPortal.jsx` (تب پروفایل یا journey), `app/services/workflow/document_service.py`

---

### گام ۱.۴ — `intro_second_semester_registration` (ترم دوم آشنایی)

- [ ] **وضعیت:** ✅ — audit: YES

| کار | UI |
|-----|-----|
| بررسی صلاحیت (درمان/تعلیق) | ⚪ popup سیستمی |
| انتخاب درس | ✅ `OperatorCourseSelectionEditor` + Quest |
| پرداخت | ✅ `SepPaymentPanel` |

**کار اختیاری:** دکمهٔ «شروع ثبت‌نام ترم ۲» وقتی `introductory_term_end` SMS فرستاده — rule در `operator_gap_rules.json` (فعلاً فقط intro/comp reg تعریف شده).

---

### گام ۱.۵ — `introductory_course_completion` (خاتمه دوره آشنایی)

- [x] **وضعیت:** ⚪ + ✅ برای **گواهی**

| کار | UI |
|-----|-----|
| دعوتنامه SMS جامع | ⚪ |
| تولید/تأیید گواهی | 👤 کمیته + ⚪ |
| **دانلود گواهی در پورتال** | ✅ **`StudentTranscriptsPanel`** |

**کار تکمیل (گام ۱.۵-الف):** نمایش گواهی signed در تب مدارک/پروفایل (`upload_certificate_to_portal` → URL در context).

---

## فاز ۲ — چرخه ترم جامع

### گام ۲.۱ — `comprehensive_term_start` (ثبت‌نام ترم جامع)

- [ ] **وضعیت:** ✅ — audit: YES

| کار | UI |
|-----|-----|
| شروع در پنجره ثبت‌نام | ✅ scheduler + `StudentQuestCard` |
| نمایش دروس + پرداخت | ✅ |
| مسدودیت مرخصی/تعلیق | ⚪ popup `blocked` |

**کار اختیاری:** CTA واضح «ثبت‌نام ترم بعد» در داشبورد وقتی instance فعال است (`studentTransitionCtaVisibility`).

---

### گام ۲.۲ — `comprehensive_term_end` (پایان ترم جامع)

- [x] **وضعیت:** ⚪ + ✅ (کارنامه — ادغام با ۱.۳-الف)

**کار تکمیل:** ادغام با گام ۱.۳-الف — یک کامپوننت `StudentTranscriptsPanel` برای هر دو فرایند.

---

### گام ۲.۳ — `student_instructor_evaluation` (ارزیابی استاد)

- [x] **وضعیت:** ✅ — پنل اختصاصی دانشجو + داشبورد مدرس و کمیته

| کار | UI |
|-----|-----|
| باز/بستن پنجره | ✅ scheduler |
| **فرم ارزیابی دانشجو** | ✅ **`StudentInstructorEvaluationPanel`** (چند درس، ناشناس، اختیاری) |
| **داشبورد مدرس** | ✅ **`InstructorEvaluationResultsPanel`** (StaffPortal / instruction) |
| **داشبورد کمیته** | ✅ **`InstructorEvaluationCommitteePanel`** (StaffPortal / course-committee) |

**فایل‌ها:** `StudentInstructorEvaluationPanel.jsx`, `student_instructor_evaluation_service.py`, `panel_routes.py`, `StaffPortal.jsx`, `StudentPortal.jsx`

**معیار پذیرش:** دانشجو هر درس را جدا ثبت کند → instance تا deadline باز بماند؛ پس از deadline نتایج در پورتال مدرس و کمیته نمایش داده شود.

---

### گام ۲.۴ — `student_non_registration` (عدم ثبت‌نام ترم)

- [x] **وضعیت:** ✅ — audit: YES (شاخه‌های دانشجو)

| کار | UI |
|-----|-----|
| جلسه کمیته | 👤 `CommitteePortal` |
| انتخاب شاخه (ثبت‌نام/مرخصی/انصراف) | ✅ `StudentQuestCard` + برچسب `branch_register` / `branch_leave` |

**کار تکمیل (گام ۲.۴-الف):** `STUDENT_TASK_LABELS_FA` برای states `branch_register`, `branch_leave` در `processMetadataLabels.js`.

---

## فاز ۳ — درمان آموزشی

### گام ۳.۱ — `start_therapy`

- [ ] **وضعیت:** ✅ — `StudentQuestCard` + انتخاب درمانگر + پرداخت

**نکته:** هفته ۹ → `week9_blocked` — فقط SMS/بلاک؛ 🔴 **UI توضیحی «چرا مسدود شدم»** می‌تواند غنی‌تر شود.

---

### گام ۳.۲ — `session_payment`

- [ ] **وضعیت:** ✅ — `SepPaymentPanel` + `form_alternate_paths`

**Quick action:** ✅ در داشبورد دانشجو.

---

### گام ۳.۳ — `attendance_tracking`

- [ ] **وضعیت:** 🟡 — دانشجو **اقدام مستقیم ندارد**؛ نتیجه در `therapy_hours_progress_fa` نمایش داده می‌شود (`student_result_visibility`).

**کار اختیاری:** نمودار پیشرفت ساعات در داشبورد.

---

### گام ۳.۴ — `fee_determination`

- [ ] **وضعیت:** ⚪ — کاملاً خودکار از والد

---

### گام ۳.۵ — `therapy_completion`

- [ ] **وضعیت:** ✅ — دکمه در `StudentQuestCard` + نمایش آستانه ۲۵۰/۷۵۰/۱۵۰

---

## فاز ۴ — سوپرویژن

### گام ۴.۱ — `supervision_50h_completion`

- [ ] **وضعیت:** 👤 سوپروایزر ثبت می‌کند — دانشجو `extra_data.lms` را می‌بیند

---

### گام ۴.۲ — `supervision_block_transition`

- [ ] **وضعیت:** ✅ — `StudentQuestCard` + `form_alternate_paths`

---

## فاز ۵ — مرخصی (جانبی)

### گام ۵.۱ — `educational_leave` / `full_education_leave`

- [x] **وضعیت:** ✅ — دانشجو: فرم درخواست + بازگشت + نمایش رد؛ کمیته: `OperatorStepFormsSection` (جلسه + تصمیم)

`full_education_leave`: audit FAIL (artifact) — 🔴 backend/ترمینال؛ UI دانشجو مشابه مرخصی موقت.

---

## فاز ۷ — کارورزی

### گام ۷.۱ — `internship_readiness_consultation`

- [x] **وضعیت:** 🟡 — audit: YES

| کار | UI |
|-----|-----|
| درخواست + قراردادها | ✅ Quest |
| **تحویل سفته حضوری** | 🟡 راهنما + بنر وضعیت در پروفایل (`promissory_note`) |
| انتخاب سوپروایزر + پرداخت | ✅ |

**کار تکمیل (گام ۷.۱-الف):** checkbox/فرم «سفته تحویل داده شد» برای staff + نمایش وضعیت به دانشجو.

---

### گام ۷.۲ — `internship_12month_conditional_review` / `intern_hours_increase`

- [ ] **وضعیت:** ⚪/👤 — عمدتاً کمیته + scheduler

---

## فاز ۸ — تکمیل دروس و دفاع

### گام ۸.۱ — خاتمه دروس (`theory_`, `skills_`, `film_`, `live_*`, `group_supervision_`)

- [x] **وضعیت:** 👤 + 🟡 — `StudentCourseStatusPanel` برای نتیجهٔ LMS

| فرایند | نقش اصلی | UI دانشجو |
|--------|---------|-----------|
| `theory_course_completion` | مدرس | 🔴 نمره/وضعیت درس در پنل نیست |
| `skills_course_completion` | مدرس | 🔴 |
| `film_observation_course_completion` | مدرس | 🔴 |
| `live_therapy_observation_course_completion` | مدرس | 🔴 |
| `live_supervision_course_completion` | مدرس | 🔴 |
| `group_supervision_course_completion` | مدرس | 🔴 |

**توضیح:** این فرایندها **طراحی‌شده برای مدرس** هستند؛ دانشجو فقط **نتیجه** (قبول/مردود) را باید ببیند.

**کار تکمیل (گام ۸.۱-الف):** تب «وضعیت دروس» در `StudentPortal` — جدول enrolled courses + grade lock status از `extra_data.lms`.

**کار تکمیل (گام ۸.۱-ب):** پنل مدرس — اطمینان از `triggerTransition` روی state `grades_entry` (Therapist/Instructor portal یا Staff).

---

### گام ۸.۲ — `article_writing_completion`

- [x] **وضعیت:** 🟡 — audit: `user_can_complete: NO` (artifact؛ CTA دانشجو فعال)

| کار | UI |
|-----|-----|
| **درخواست دفاع (مهلت ۸ روز)** | ✅ CTA + راهنمای `class_closed_student` در Quest |
| ارزیابی مدرس | 👤 |

**کار تکمیل (گام ۸.۲-الف):** فرم + CTA در `StudentQuestCard` برای state دانشجو؛ ثبت در `form_alternate_paths`.

---

### گام ۸.۳ — `thesis_defense_request`

- [ ] **وضعیت:** ✅ — audit: **Section A** (آماده تحویل)

| کار | UI |
|-----|-----|
| بررسی ۴ شرط + آپلود گزارش سایکوتیک | ✅ Quest + forms |
| بارگذاری پایان‌نامه / اصلاح | ✅ `revision_upload` در metadata labels |
| کمیته‌ها | 👤 `CommitteePortal` |

**کار اختیاری:** نمایش پیشرفت شرط‌ها (۶۷ واحد، ساعات) قبل از شروع فرایند.

---

## فهرست اولویت‌بندی‌شده (ترتیب پیشنهادی تکمیل)

| # | گام | تلاش | اثر |
|---|-----|------|-----|
| 1 | ۰.۱-الف / ۰.۲-الف — UI مصاحبه‌گر | متوسط | رفع گلوگاه ثبت‌نام |
| 2 | ۱.۳-الف / ۲.۲ — دانلود کارنامه | متوسط | شفافیت پس از هر ترم |
| 3 | ۲.۳-الف — ارزیابی استاد | کم | الزام هر ترم |
| 4 | ۸.۲-الف — مقاله‌نویسی / درخواست دفاع | متوسط | نزدیک فارغ‌التحصیلی |
| 5 | ۸.۱-الف — وضعیت دروس دانشجو | متوسط | کل مسیر جامع |
| 6 | ۱.۵-الف — دانلود گواهی آشنایی | کم | پس از ۱۰ درس |
| 7 | ۰.۲-ب — auto-start ثبت‌نام جامع | کم | UX بهتر |
| 8 | ۱.۲-الف — نمایش غیبت کلاس | کم | پیشگیری از Incomplete |
| 9 | ۲.۴-الف — راهنمای non_registration | کم | کاهش انصراف |
| 10 | ۷.۱-الف — UI سفته انترn | کم | کارورزی |

---

## پیوست — نگاشت audit → UI (فرایندهای مسیر)

| code | user_can_complete (audit) | form_alternate_paths | partial_ui |
|------|---------------------------|----------------------|------------|
| introductory_course_registration | YES | — | — |
| comprehensive_course_registration | YES | — | — |
| intro_second_semester_registration | YES | — | — |
| comprehensive_term_start | YES | — | — |
| comprehensive_term_end | YES | — | — |
| introductory_term_end | YES | — | — |
| lesson_start_per_term | YES | ✅ | — |
| start_therapy | YES | — | — |
| session_payment | YES | ✅ | — |
| therapy_completion | YES | — | — |
| supervision_block_transition | YES | ✅ | — |
| attendance_tracking | YES | ✅ (therapist) | — |
| educational_leave | YES | — | — |
| internship_readiness_consultation | YES | — | — |
| student_non_registration | YES | — | — |
| thesis_defense_request | YES (Sec A) | — | — |
| introductory_course_completion | YES | ✅ (LMS) | — |
| student_instructor_evaluation | **NO** | ✅ | — |
| class_attendance | **NO** | — | — (نمایش در `StudentCourseStatusPanel`) |
| article_writing_completion | **NO** | ✅ | — |
| theory/skills/film/live/group completion | **NO** | — | — |

---

## پس از هر گام تکمیل‌شده

1. به‌روزرسانی `metadata/customer_acceptance_alternate_paths.json` در صورت مسیر UI جدید
2. اجرا: `python scripts/audit_customer_acceptance.py` — هدف: افزایش Readiness برای فرایند مربوط
3. تیک زدن checkbox این سند
4. (اختیاری) یک خط در `metadata/process_registry/GAPS.json` → `resolved_*` اگر شکاف بسته شد

---

*این سند مکمل `docs/role_web_tasks_gap_matrix.md` است و فقط روی **مسیر تحصیلی دانشجو** متمرکز است.*
