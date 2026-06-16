# سند مرجع: وظایف وب بر اساس نقش و فرایند

**نسخه سند:** 1.1  
**تاریخ:** 2026-04-18  
**هدف:** مرجع چندمرحله‌ای برای تطبیق انتظارات محصول با وضعیت فعلی کد، ثبت نواقص، و اولویت‌بندی تکمیل در فازهای بعد — **بدون الزام به تغییر کد در همین گام.**

**تغییرات ۱.۱:** صندوق نمونهٔ فرایند برای نقش‌های ورود (`GET /api/panel/my-process-inbox`)، ادغام با تب pending کارمند، اسلات مصاحبه با نقش `interviewer` و فیلد `interviewer_user_id`، به‌روزرسانی ماتریس بخش ۱ و توضیح ردیف `finance`.

### پایلوت و معیار (ثبت برای تیم)

**پایلوت صندوق:** ابتدا **کارمند** (`staff`) و **مصاحبه‌گر** (`interviewer`) — صندوق از [`build_portal_role_process_inbox`](app/services/portal_role_inbox.py) و UI [`PortalProcessInbox`](admin-ui/src/components/PortalProcessInbox.jsx).  
**معیار تکمیل:** همان سه بند بخش ۰؛ برای صندوق، نمایش حداقل یک لینک عمیق معتبر به همان `instance_id` کافی است.

---

## نحوهٔ خواندن (چند مرحله)

| مرحله | بخش | زمان تقریبی |
|--------|-----|-------------|
| 1 | [بخش ۰](#بخش-۰--اصول-واژه‌ها-و-معیار-تکمیل) — اصول و معیار | ۵ دقیقه |
| 2 | [بخش ۱](#بخش-۱--ماتریس-نقش-×-نوع-وظیفه-در-وب) — ماتریس نقش‌ها | ۱۵–۲۰ دقیقه |
| 3 | [بخش ۲](#بخش-۲--برش-عمودی-مصاحبه-نمونه) — نمونهٔ مصاحبه | ۱۰ دقیقه |
| 4 | [بخش ۳](#بخش-۳--استخراج-سیستماتیک-فرایندها-و-نواقص) — روش و جدول فشرده | ۱۰ دقیقه + تکمیل تدریجی |
| 5 | [بخش ۴](#بخش-۴--نقشهٔ-راه-فازها-چک‌لیست) — نقشهٔ راه و چک‌لیست | ۵ دقیقه |
| 6 | [بخش ۵](#بخش-۵--مرور-ذی‌نفعان-خارج-از-مخزن) — مرور تیم | جلسهٔ کوتاه |

---

## بخش ۰ — اصول، واژه‌ها، و معیار تکمیل

### واژه‌ها

| اصطلاح | معنی در این سند |
|--------|-----------------|
| **نقش ورود (portal role)** | مقدار `User.role` پس از ورود؛ همان که منوی پنل و مجوزها بر اساس آن است (مثلاً `staff`, `interviewer`). |
| **نقش مرحله (assigned_role)** | مقدار `assigned_role` روی **state** در `metadata/processes/*.json`؛ تعیین می‌کند «این مرحله از نظر طراحی فرایند متعلق به کدام نقش منطقی است». |
| **کاتالوگ نقش** | خروجی [`GET /api/panel/action-queue`](app/api/panel_routes.py) → [`get_panel_action_queue_for_role`](app/meta/student_lifecycle_matrix.py) + نمایش در [`PanelRoleActionQueue`](admin-ui/src/components/PanelRoleActionQueue.jsx): **فهرست مراحل متادیتا و الگوهای متنی** — **نه** شمارندهٔ پروندهٔ باز. |
| **صندوق اقدام واقعی (هدف محصول)** | فهرست **نمونه‌های فرایند** (`ProcessInstance`) که در وضعیت فعلی نیاز به اقدام نقش دارند، با **لینک مستقیم** به همان پرونده در پنل (مثلاً `?instance_id=...&tab=pending`). پیاده‌سازی فعلی: [`GET /api/panel/my-process-inbox`](app/api/panel_routes.py) + [`PortalProcessInbox`](admin-ui/src/components/PortalProcessInbox.jsx). |
| **پیاده / جزئی / خالی** | **پیاده:** مسیر در UI+API وجود دارد. **جزئی:** بخشی هست (مثلاً فقط لیست بدون لینک عمیق، یا فقط کارمند نه نقش تخصصی). **خالی:** در پنل وب آن نقش، مسیر مستقیم دیده نمی‌شود. |

### معیار «تکمیل» برای یک وظیفهٔ وب (قابل استفاده در تیک زدن بعدی)

1. کاربر نقش مربوطه می‌تواند **بدون تکیه بر ادمین** عمل را شروع/ثبت کند (مگر SOP استثناء صریح).
2. از داشبورد یا صفحهٔ اصلی نقش، **حداکثر ۱–۲ کلیک** تا رسیدن به همان فرم/ترنزیشن (یا لینک عمیق مستند شده).
3. در صورت نیاز، **دادهٔ خروجی** (مثلاً نتیجهٔ مصاحبه) در **پروفایل/رزومهٔ منطقی** دانشجو قابل اتکا برای فرایندهای بعدی باشد (یا مسیر ذخیرهٔ آن در `context_data` / مدل مرتبط مشخص باشد).

### منابع حقیقت در مخزن

| منبع | مسیر |
|------|------|
| نقش‌های ثبت‌شده (با مجوز) | [`metadata/roles.json`](metadata/roles.json) — **توجه:** نقش‌هایی مثل `interviewer` و `finance` در منوی [`Layout.jsx`](admin-ui/src/components/Layout.jsx) هستند اما در این فایل **همیشه** ردیف ندارند؛ در ماتریس با یادداشت «فقط پنل» آمده‌اند. |
| نگاشت پنل → assigned_role | [`metadata/portal_role_assigned_role_map.json`](metadata/portal_role_assigned_role_map.json) |
| فهرست فرایندها | [`metadata/process_registry/INDEX.json`](metadata/process_registry/INDEX.json) — **حدود ۷۳** فرایند با فیلد `code` (شمارش خودکار؛ با تکامل رجیستری تغییر می‌کند). |
| کاتالوگ مراحل به تفکیک نقش اپراتوری | [`app/meta/operator_state_catalog.py`](app/meta/operator_state_catalog.py) (`get_state_catalog_for_portal_role`) |

---

## بخش ۱ — ماتریس نقش × نوع وظیفه در وب

**راهنمای ستون‌ها:** برای هر **نقش ورود** یک سطر؛ هر ستون یک **نوع کار** در وب. وضعیت: **پیاده** | **جزئی** | **خالی**.

| نقش ورود | نام فارسی (مرجع) | تعریف زمان / منبع (اسلات، تقویم، لینک جلسه) | اقدام روی فرایند (ترنزیشن، تایید/رد) | فرم / سند پویا | پرداخت / مالی | جلسه آنلاین / لینک | مشاهده رزومه / پروفایل دانشجو | یادداشت نواقص کوتاه |
|----------|-------------------|---------------------------------------------|----------------------------------------|----------------|-----------------|---------------------|--------------------------------|---------------------|
| `student` | دانشجو | جزئی — [`InterviewSlotPicker`](admin-ui/src/components/InterviewSlotPicker)، جلسات درمانی، تکالیف | پیاده — [`StudentPortal`](admin-ui/src/pages/StudentPortal.jsx)، [`StudentQuestCard`](admin-ui/src/components/StudentQuestCard.jsx) | پیاده — فرم‌های مرحله فرایند | پیاده — callback پرداخت | جزئی — تب جلسات آنلاین | پیاده — پروفایل دانشجو | صندوق متمرکز با نام یکسان محدود است؛ مسیر اصلی از داشبورد/کارت مسیر است. |
| `staff` | کارمند دفتر | پیاده — [`InterviewSlotsAdmin`](admin-ui/src/components/InterviewSlotsAdmin) در [`StaffPortal`](admin-ui/src/pages/StaffPortal.jsx) | **پیاده** — [`GET /api/panel/my-process-inbox`](app/api/panel_routes.py) + ادغام ترتیب با تب pending؛ [`isWaitingForStaff`](admin-ui/src/pages/StaffPortal.jsx) برای موارد خارج از صندوق باقی مانده | پیاده — فرایندها و اسناد | جزئی — وابسته به دسترسی | جزئی — مشاهده رزروها [`InterviewBookingsPanel`](admin-ui/src/components/InterviewBookingsPanel.jsx) | پیاده — ردیابی دانشجو | تکلیف بدون نمره در صندوق staff؛ هم‌راستاسازی کامل با بخش ۳ در تدریج. |
| `interviewer` | مصاحبه‌گر | **پیاده** — نقش در [`MANAGE_ROLES`](app/api/interview_slots_routes.py)؛ فیلد `interviewer_user_id` روی [`InterviewSlot`](app/models/operational_models.py)؛ [`InterviewSlotsAdmin`](admin-ui/src/components/InterviewSlotsAdmin.jsx) در [`InterviewerPortal`](admin-ui/src/pages/InterviewerPortal.jsx) | **جزئی** — [`PortalProcessInbox`](admin-ui/src/components/PortalProcessInbox.jsx) + لینک به staff برای ترنزیشن؛ فرم کامل همان نمونه هنوز در UI مصاحبه‌گر تعبیه نشده | جزئی — راهنمای action-queue با [`ROLE_ACTION_PATTERNS`](app/meta/student_lifecycle_matrix.py) برای interviewer | — | پیاده — رزروها [`InterviewBookingsPanel`](admin-ui/src/components/InterviewBookingsPanel.jsx) | از مسیر staff/student | **باقی‌مانده:** فرم اجرای ترنزیشن در خود پنل مصاحبه‌گر (بدون مراجعه به staff). |
| `site_manager` | مسئول سایت | پیاده — اسلات + [`SiteManagerPortal`](admin-ui/src/pages/SiteManagerPortal.jsx) | جزئی — هشدار حضور و غیره | جزئی | — | جزئی | پیاده | کاتالوگ مراحل در action-queue؛ صندوق instance-based کامل نیست. |
| `deputy_education` | معاون آموزش | پیاده — اسلات (مدیریت) | پیاده — [`CommitteePortal`](admin-ui/src/pages/CommitteePortal.jsx) شاخه‌های متعدد | جزئی | — | جزئی | پیاده | |
| `therapist` | درمانگر | جزئی — تقویم/جلسات درمانی API | پیاده — [`TherapistPortal`](admin-ui/src/pages/TherapistPortal.jsx) / ردیابی | جزئی | — | پیاده — جلسات | پیاده | |
| `supervisor` | سوپروایزر | جزئی | پیاده — [`SupervisorPortal`](admin-ui/src/pages/SupervisorPortal.jsx) بررسی‌ها | جزئی | — | جزئی | پیاده | |
| `finance` | اپراتور مالی | — | جزئی — داشبورد مالی [`/panel/finance`](admin-ui/src/components/Layout.jsx) | — | پیاده | — | جزئی | **تعمدی:** در [`portal_role_assigned_role_map.json`](metadata/portal_role_assigned_role_map.json) فیلد `assigned_roles` برای `finance` خالی است؛ وظایف مالی از مسیر داشبورد مالی و گزارش‌هاست، نه از لیست مراحل فرایند. صندوق [`my-process-inbox`](app/api/panel_routes.py) برای این نقش هم خالی است. |
| `admin` | مدیر سیستم | پیاده | پیاده | پیاده | پیاده | پیاده | پیاده | [`operator_followup_inbox`](app/services/operator_followup_inbox.py) برای مدیر اصلی؛ صندوق [`my-process-inbox`](app/api/panel_routes.py) همهٔ نقش‌های اپراتوری را برای ادمین می‌آورد (نگاشت `include_all`). |
| کمیته‌ها (`progress_committee`, `education_committee`, `supervision_committee`, `specialized_commission`, `therapy_committee_*`) | متنوع | جزئی | پیاده — [`CommitteePortal`](admin-ui/src/pages/CommitteePortal.jsx) با شمارنده بررسی | جزئی | — | جزئی | پیاده | نگاشت در [`portal_role_assigned_role_map.json`](metadata/portal_role_assigned_role_map.json). |
| `monitoring_committee_officer` | مسئول کمیته نظارت | جزئی | پیاده — CommitteePortal | جزئی | — | جزئی | پیاده | |

**جمع‌بندی بخش ۱:** شکاف «کاتالوگ vs صندوق واقعی» با **my-process-inbox** برای نقش‌های اپراتوری کاهش یافته؛ **کارمند** و **مصاحبه‌گر** اکنون از صندوق + لینک عمیق استفاده می‌کنند. **دانشجو** همچنان کارت مسیر؛ **کمیته/سوپروایزر** شمارنده بررسی؛ **مدیر** operator followup + صندوق عمومی.

---

## بخش ۲ — برش عمودی «مصاحبه» (نمونه)

جریان **هدف محصول** (خلاصه):

1. وقتی فرایند به مرحلهٔ مصاحبه می‌رسد، **مصاحبه‌گر** در پنل خود **زمان‌های قابل رزرو** تعریف کند.
2. **دانشجو** از پروفایل/فرایند، **اسلات** را انتخاب کند.
3. **قبل و حین** زمان مصاحبه، **لینک جلسه آنلاین** (در صورت `mode=online`) برای طرفین **در همان ساعت** قابل مشاهده باشد.
4. پس از جلسه، **مصاحبه‌گر** در **پنل خودش** نتیجه را ثبت کند و فرایند ادامه یابد.
5. دادهٔ لازم در **پروفایل/رزومهٔ دانشجو** برای فرایندهای بعدی **قابل اتکا** ذخیره شود.

### تطبیق گام‌به‌گام با کد فعلی

| گام هدف | وضعیت | ارجاع کد / یادداشت |
|---------|--------|---------------------|
| تعریف اسلات توسط مصاحبه‌گر | **پیاده** | [`MANAGE_ROLES`](app/api/interview_slots_routes.py) شامل `interviewer`؛ فیلد `interviewer_user_id` در [`InterviewSlot`](app/models/operational_models.py) (مهاجرت `015_interview_slot_interviewer_user`). |
| تعریف اسلات توسط کارمند/سایت/معاون | **پیاده** | [`InterviewSlotsAdmin`](admin-ui/src/components/InterviewSlotsAdmin.jsx)، API `POST /api/interview-slots/manage`. |
| رزرو توسط دانشجو | **پیاده** | [`InterviewSlotPicker`](admin-ui/src/components/InterviewSlotPicker.jsx)، `POST /api/interview-slots/book`، سرویس [`book_slot_for_registration`](app/services/interview_slot_service.py). |
| نمایش لینک جلسه | **جزئی** | فیلدهای `mode`, `meeting_link`, `location_fa` روی اسلات؛ نمایش در جدول رزروها [`InterviewBookingsPanel`](admin-ui/src/components/InterviewBookingsPanel.jsx). **قید «فقط در بازهٔ زمانی»** در UI به‌صورت صریح مستند/پیاده نشده است. |
| ثبت نتیجه توسط مصاحبه‌گر در پنل مصاحبه‌گر | **جزئی** | [`InterviewerPortal`](admin-ui/src/pages/InterviewerPortal.jsx): [`PortalProcessInbox`](admin-ui/src/components/PortalProcessInbox.jsx) لینک به همان نمونه (غالباً `StaffPortal` pending)؛ UI فرم ترنزیشن همان‌جا هنوز کامل نیست. |
| ادامهٔ فرایند پس از نتیجه | **جزئی** | stateهایی مانند `interview_completed` در heuristic [`isWaitingForStaff`](admin-ui/src/pages/StaffPortal.jsx) — نه اختصاص به نقش `interviewer` در UI. |
| ماندگاری در رزومه/پروفایل | **جزئی** | بسته به ذخیره در `context_data` فرایند ثبت‌نام؛ نیاز به تسویهٔ SOP داده و فیلدهای نمایش در پروفایل. |

### فایل‌های کلیدی (مصاحبه)

| موضوع | مسیر |
|--------|------|
| API اسلات | [`app/api/interview_slots_routes.py`](app/api/interview_slots_routes.py) |
| مدل | [`app/models/operational_models.py`](app/models/operational_models.py) — کلاس `InterviewSlot` |
| پنل مصاحبه‌گر | [`admin-ui/src/pages/InterviewerPortal.jsx`](admin-ui/src/pages/InterviewerPortal.jsx) |
| پنل کارمند (pending + اسلات) | [`admin-ui/src/pages/StaffPortal.jsx`](admin-ui/src/pages/StaffPortal.jsx) |
| دانشجو — انتخاب اسلات | [`admin-ui/src/pages/StudentPortal.jsx`](admin-ui/src/pages/StudentPortal.jsx) + `InterviewSlotPicker` |

---

## بخش ۳ — استخراج سیستماتیک فرایندها و نواقص

### روش تکمیل‌پذیر (بدون حدس زدن دستی برای ۷۰+ فرایند)

1. برای هر فایل در `metadata/processes/*.json`، تمام **states** را بخوانید که `assigned_role` آن‌ها در [`exclude_from_operator_catalog`](metadata/portal_role_assigned_role_map.json) نیست.
2. با [`portal_role_assigned_role_map.json`](metadata/portal_role_assigned_role_map.json) ببینید آن `assigned_role` به **کدام نقش ورود** می‌رسد (یا فقط از طریق staff با چند نقش منطقی پوشش داده می‌شود).
3. برای هر جفت `(process_code, state_code)` بررسی کنید: آیا در پنل مربوطه، **مسیر اجرای ترنزیشن** یا **فرم مرحله** با همان نقش قابل دسترسی است؟
4. اسکریپت [`scripts/audit_process_ui_clicks.py`](scripts/audit_process_ui_clicks.py) (در صورت استفاده در پروژه) می‌تواند به عنوان کمک **کلیک‌پذیری** کنار این جدول استفاده شود — جایگزین قضاوت محصول نیست.

### جدول فشردهٔ نمونه (نمونه‌هایی از فرایندها — قابل گسترش)

| فرایند (code) | نقش‌های اپراتوریِ نمونه (از INDEX / متادیتا) | پنل غالب فعلی | شکاف احتمالی |
|---------------|---------------------------------------------|----------------|--------------|
| `introductory_course_registration` / `comprehensive_course_registration` | `interviewer`, `admissions_officer`, … | دانشجو + کارمند + مصاحبه‌گر (جزئی) | صندوق واحد per-role؛ مصاحبه‌گر بدون تعریف اسلات |
| `fall_semester_preparation` / `winter_semester_preparation` | چند نقش مدیریتی و کمیته | Committee / Deputy / Site | بیشتر اعلان SLA است تا inbox عمیق |
| `attendance_tracking` | `therapist`, `site_manager`, `deputy_education` | Therapist / Site / Deputy | همگرایی با هشدارها |
| `session_payment` | `system` + دانشجو | دانشجو | نقش اپراتور کم |
| `educational_leave` | `progress_committee`, `deputy_education`, `student` | CommitteePortal / Student | OK نسبی |

**سطرهای تکمیلی:** تیم محصول می‌تواند از خروجی [`get_state_catalog_for_portal_role`](app/meta/operator_state_catalog.py) برای هر نقش، جدول را در صفحهٔ زیرمجموعه یا spreadsheet تکمیل کند.

---

## بخش ۴ — نقشهٔ راه فازها (چک‌لیست)

برای هر فاز، تیک بزنید وقتی **خروجی** مشخص تحقق یافت.

### فاز A — تثبیت سند و هم‌خوانی نام‌ها

- [ ] A1: مرور [`metadata/roles.json`](metadata/roles.json) با [`Layout.jsx`](admin-ui/src/components/Layout.jsx) — نقش‌های فقط-پنل (مثل `interviewer`, `finance`) در سند ثبت شدند.
- [ ] A2: تأیید ذی‌نفع محصول روی **معیار تکمیل** بخش ۰.
- [ ] A3: تعیین مالک نگهداری این فایل markdown در مخزن.

### فاز B — صندوق اقدام مبتنی بر `ProcessInstance` (پایلوت)

- [ ] B1: انتخاب **یک نقش پایلوت** (پیشنهاد: `interviewer` یا `staff`).
- [ ] B2: طراحی API (یا گسترش موجود) که فقط نمونه‌های باز همان نقش را برگرداند — الگو: [`operator_followup_inbox`](app/services/operator_followup_inbox.py).
- [ ] B3: اتصال UI به لینک عمیق (`instance_id`, تب) — الگو: [`usePortalInstanceDeepLink`](admin-ui/src/hooks/usePortalInstanceDeepLink.js).
- [ ] B4: تست دستی یک سناریوی کامل.

### فاز C — مسیر مصاحبهٔ سرتاسری

- [ ] C1: تصمیم مدل داده: مالک اسلات (مصاحبه‌گر) + سیاست رزرو.
- [ ] C2: مجوز API `manage` برای نقش مصاحبه‌گر (در صورت تأیید) یا جایگزین workflow.
- [ ] C3: ثبت نتیجه در `InterviewerPortal` یا ادغام کنترل‌شده با فرم فرایند.
- [ ] C4: نمایش خلاصه در پروفایل دانشجو / `context_data` طبق SOP.

### فاز D — تعمیم به سایر نقش‌ها

- [ ] D1: تکمیل جدول بخش ۳ برای همهٔ فرایندهای [`INDEX.json`](metadata/process_registry/INDEX.json).
- [ ] D2: حذف یا کاهش وابستگی [`isWaitingForStaff`](admin-ui/src/pages/StaffPortal.jsx) به نفع نگاشت `assigned_role`.
- [ ] D3: مستندسازی برای کاربر نهایی (راهنمای پنل).

---

## بخش ۵ — مرور ذی‌نفعان (خارج از مخزن)

این بخش **کار دستی تیم** است؛ در مخزن فقط چک‌لیست نگه داشته می‌شود.

- [ ] جلسهٔ ۳۰ دقیقه‌ای: نمایش «کاتالوگ فعلی» در مقابل «صندوق واقعی مطلوب».
- [ ] اولویت‌بندی فاز B vs C با توجه به ظرفیت تیم.
- [ ] تأیید نهایی نام فارسی نقش‌ها در UI با اسناد آموزشی موسسه.

---

## پیوست — فایل‌های مرجع سریع

| موضوع | مسیر |
|--------|------|
| راهنمای اقدام نقش (کاتالوگ) | [`app/meta/student_lifecycle_matrix.py`](app/meta/student_lifecycle_matrix.py) — `ROLE_ACTION_PATTERNS`, `get_panel_action_queue_for_role` |
| نگاشت پنل | [`metadata/portal_role_assigned_role_map.json`](metadata/portal_role_assigned_role_map.json) |
| کاتالوگ state | [`app/meta/operator_state_catalog.py`](app/meta/operator_state_catalog.py) |
| صندوق اپراتور (مدیر) | [`app/services/operator_followup_inbox.py`](app/services/operator_followup_inbox.py) |
| صندوق نمونهٔ فرایند (نقش ورود) | [`app/services/portal_role_inbox.py`](app/services/portal_role_inbox.py) — `GET /api/panel/my-process-inbox` در [`app/api/panel_routes.py`](app/api/panel_routes.py) |
| ناوبری پنل | [`admin-ui/src/components/Layout.jsx`](admin-ui/src/components/Layout.jsx) |

---

*پایان سند نسخه ۱.۱ — برای به‌روزرسانی، تاریخ و نسخه را افزایش دهید و تغییرات را در یک خط خلاصه کنید.*
