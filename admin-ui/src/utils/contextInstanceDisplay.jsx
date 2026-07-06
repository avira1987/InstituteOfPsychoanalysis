import { PROCESS_LABELS_FA, STATE_LABELS_FA } from './processMetadataLabels'
import { parseStepFileUploadValue, resolveUploadPublicUrl } from './uploadPublicUrl'
import { formatShamsiTehran } from './shamsiDateTime'

/** برچسب‌های ثابت برای کلیدهای رایج در context_data */
export const CONTEXT_KEY_LABELS = {
  notes: 'یادداشت ثبت‌شده',
  interview_result: 'نتیجهٔ مصاحبه',
  weekly_sessions: 'تعداد جلسات هفتگی',
  from_state: 'مرحلهٔ قبل از انتقال',
  to_state: 'مرحلهٔ بعد از انتقال',
  termination_requests: 'درخواست‌های خاتمه',
  reminder_45_48_sent_at: 'زمان ارسال یادآور (۴۵–۴۸ ساعت)',
  student_status: 'وضعیت دانشجو (در پرونده)',
  amount: 'مبلغ',
  decision: 'تصمیم',
  interview_result_submitted: 'ثبت نتیجهٔ مصاحبه',
  return_reminder_at: 'یادآور بازگشت',
  return_deadline_at: 'مهلت ثبت‌نام پس از یادآوری',
  therapy_first_session_at: 'تاریخ شروع درمان آموزشی (بازگشت)',
  supervision_first_session_at: 'تاریخ شروع سوپرویژن (بازگشت)',
  therapy_payment_amount_rial: 'مبلغ پرداخت جلسه اول درمان (ریال)',
  supervision_payment_amount_rial: 'مبلغ پرداخت جلسه اول سوپرویژن (ریال)',
  registration_unlocked_at: 'زمان بازگشایی ثبت‌نام دروس',
  return_completed_at: 'زمان تکمیل بازگشت به کل آموزش',
  course_type_display_fa: 'نوع دوره',
  is_intern_display_fa: 'وضعیت بالینی',
  weekly_hours_hint_fa: 'محدودیت ساعات درمان',
  supervision_hours_hint_fa: 'محدودیت ساعات سوپرویژن',
  leave_schedule_set_at: 'زمان تنظیم تقویم بازگشت',
  committee_meeting_at: 'زمان جلسه کمیته (ثبت‌شده در سامانه)',
  committee_meeting_mode: 'نحوهٔ جلسه کمیته',
  committee_meeting_link: 'لینک جلسه آنلاین',
  committee_meeting_location_fa: 'محل یا آدرس جلسه',
  student_portal_alert_fa: 'هشدار نمایش داده‌شده به دانشجو',
  logged_at: 'زمان ثبت',
  payload: 'جزئیات',
  admission_type: 'نوع پذیرش',
  allowed_course_count: 'تعداد دروس مجاز',
  therapist_id: 'شناسه درمانگر',
  new_supervisor_id: 'شناسه سوپروایزر جدید',
  session_credit_balance: 'موجودی اعتبار جلسه',
  supervision_attendance_recorded: 'ثبت حضور در سوپرویژن',
  live_supervision_normal_count: 'تعداد حضور عادی سوپرویژن زنده',
  live_supervision_mirror_count: 'تعداد حضور پشت‌آینه',
  mirror_session_index: 'شماره جلسه پشت‌آینه',
  mirror_implementation_text: 'متن پیاده‌سازی پشت‌آینه',
  compensation_pending: 'جلسات پرداخت جبرانی معوق',
  compensation_payment_url: 'لینک پرداخت جبرانی',
  session_payment_forfeited: 'جلسه بدون بازپرداخت (مصادره)',
  forfeit_amount: 'مبلغ باقی‌ماندهٔ غیرقابل‌بازگشت',
  invoice_amount: 'مبلغ فاکتور',
  last_session_link: 'لینک جلسه آنلاین',
  therapy_session_id: 'شناسهٔ جلسهٔ درمان (ثبت‌شده)',
  payment_amount_rial: 'مبلغ پرداخت (ریال)',
  agreed_session_date: 'تاریخ توافق‌شدهٔ جلسه',
  agreed_session_time: 'ساعت توافق‌شدهٔ جلسه',
  preferred_date: 'تاریخ پیشنهادی جلسه',
  preferred_time: 'ساعت پیشنهادی جلسه',
  request_note: 'توضیح درخواست',
  alternative_date: 'تاریخ جایگزین پیشنهادی درمانگر',
  alternative_time: 'ساعت جایگزین پیشنهادی درمانگر',
  confirmed_alternative_date: 'تاریخ تأییدشدهٔ جلسه',
  confirmed_alternative_time: 'ساعت تأییدشدهٔ جلسه',
  new_preferred_date: 'تاریخ جدید پیشنهادی',
  new_preferred_time: 'ساعت جدید پیشنهادی',
  extra_session_calendar_summary_fa: 'خلاصهٔ ثبت تقویم (جلسه اضافی)',
  extra_session_calendar_noted_at: 'زمان یادداشت تقویم',
  therapy_status: 'وضعیت درمان آموزشی',
  payment_unlocked_for_50th_session: 'امکان پرداخت جلسه ۵۰ام فعال شد',
  supervisor_slot_removed_from_available: 'حذف از وقت‌های آزاد سوپروایزر',
  accumulated_therapy_hours: 'ساعت‌های تجمعی درمان',
  payment_method: 'روش پرداخت',
  payment_method_selected: 'انتخاب روش پرداخت',
  installment_count: 'تعداد اقساط',
  pending_installments_remaining: 'تعداد اقساط باقی‌مانده',
  next_installment_due_at: 'سررسید قسط بعدی',
  term_start_date: 'تاریخ شروع ترم',
  term_code: 'کد ترم',
  term_gpa: 'معدل ترم',
  cumulative_gpa: 'معدل کل',
  failed_courses: 'دروس مردود',
  next_term_registration_deadline: 'مهلت ثبت‌نام ترم بعد',
  next_term_registration_blocked: 'مسدودیت ثبت‌نام ترم بعد',
  weeks_since_start: 'هفته‌های گذشته از شروع کلاس‌ها',
  weeks_since_term_start: 'هفته‌های گذشته از شروع ترم',
  non_registration_decision: 'تصمیم جلسه عدم ثبت‌نام',
  branch_register_entered_at: 'شروع مهلت ثبت‌نام ۲ روزه',
  branch_register_deadline_at: 'پایان مهلت ثبت‌نام ۲ روزه',
  branch_leave_entered_at: 'شروع مهلت مرخصی ۳ روزه',
  branch_leave_deadline_at: 'پایان مهلت مرخصی ۳ روزه',
  meeting_datetime: 'تاریخ و ساعت جلسه کمیته نظارت',
  meeting_held: 'جلسه برگزار شد',
  referral_conditions: 'شرایط ارجاع',
  referral_conditions_set_at: 'زمان ثبت شرایط ارجاع',
  patient_referral_rows: 'لیست بیماران ارجاع',
  patient_first_name: 'نام بیمار',
  patient_last_name: 'نام خانوادگی بیمار',
  patient_phone: 'شماره تماس بیمار',
  referral_notes: 'توضیحات پذیرش',
  instructor_id: 'مدرس کلاس',
  session_time: 'ساعت شروع جلسه',
  session_time_registered: 'زمان در LMS ثبت شد',
  student_patient_log_entered_at: 'شروع مهلت تماس با بیماران',
  general_therapy_committee_review_entered_at: 'ورود به بررسی کمیته درمان',
  coordination_followup_entered_at: 'شروع مهلت پیگیری هماهنگی',
  followup_in_progress_entered_at: 'زمان ورود به پیگیری افت تحصیلی',
  total_score: 'نمره نهایی درس',
  result_status: 'نتیجه (قبول/مردود)',
  average_score: 'میانگین نمره',
  participation_rate: 'میزان مشارکت',
  participation_score: 'نمره مشارکت',
  attendance_score: 'نمره حضور',
  ta_total_score: 'نمره کل کمک‌مدرس',
  ta_pass_fail: 'وضعیت TA',
  absence_count: 'تعداد غیبت',
  class_absence_count: 'غیبت کلاس',
  term_absence_count: 'غیبت ترم',
  teaching_assistant: 'کمک‌مدرس',
  ta_name: 'نام کمک‌مدرس',
  students_grades: 'نمرات دانشجویان',
  grade: 'نمره',
  course_name: 'نام درس',
  source_course_name: 'درس مبدأ',
  source_course_code: 'کد درس مبدأ',
  next_course_name: 'درس بعدی',
  next_course_code: 'کد درس بعدی',
  track_name: 'نام رسته',
  track_code: 'کد رسته',
  upgrade_applied_at: 'زمان اعمال ارتقا',
  promoted_role: 'نقش جدید',
  current_rank: 'رتبه تحلیلی فعلی',
  current_analytic_rank_fa: 'رتبه تحلیلی فعلی',
  ta_pass_count: 'تعداد پاس موفق TA',
  ta_upgrade_summary_fa: 'خلاصه احراز ارتقا',
  already_assistant_faculty: 'قبلاً دستیار هیئت علمی',
  student_portal_message_fa: 'پیام پورتال',
  manual_retry_available: 'امکان درخواست مجدد',
  eligibility_summary_fa: 'خلاصه احراز شرایط',
  eligible: 'احراز شرایط ارتقا',
  rank_ok: 'رتبه دستیار هیئت علمی',
  passes_ok: 'دو بار پاس موفق',
  session_index: 'شماره جلسه',
  session_number: 'شماره جلسه',
  milestone_session: 'جلسه milestone',
  lesson_course_label: 'نام درس',
  online_class_link: 'لینک ورود به کلاس آنلاین',
  teaching_assistant_name: 'نام کمک‌مدرس',
  selected_courses: 'دروس انتخاب‌شده',
  source: 'منبع ثبت در سامانه',
  parent_start_therapy_instance_id: 'شناسهٔ فرایند آغاز درمان (فنی)',
  parent_instance_id: 'فرایند مرتبط (والد)',
  violation_registration_instance_id: 'پروندهٔ ثبت تخلف (فرایند ۵۵)',
  et_eligibility_met: 'احراز شروط ارتقا',
  et_eligibility_summary_fa: 'خلاصه احراز شرایط',
  ta_eligibility_met: 'احراز شروط ارتقا به کمک‌مدرس',
  ta_eligibility_summary_fa: 'خلاصه احراز شرایط کمک‌مدرس',
  ta_cumulative_gpa: 'معدل',
  ta_therapy_hours_completed: 'ساعات درمان آموزشی',
  tracks: 'رسته‌های کمک‌مدرس',
  step_otp_verified: 'تأیید پیامکی',
  et_therapy_active: 'درمان شخصی فعال',
  et_therapy_weekly_sessions: 'جلسات هفتگی درمان',
  et_therapy_hours_completed: 'ساعات درمان تکمیل‌شده',
  et_therapy_hours_remaining: 'ساعات درمان باقیمانده',
  et_supervision_active: 'سوپرویژن فعال',
  et_supervision_monthly_sessions: 'جلسات ماهانه سوپرویژن',
  et_supervision_hours_completed: 'ساعات سوپرویژن تکمیل‌شده',
  et_supervision_hours_remaining: 'ساعات سوپرویژن باقیمانده',
  selected_therapist_label: 'درمانگر انتخاب‌شده',
  selected_supervisor_label: 'سوپروایزر انتخاب‌شده',
  et_slot_1: 'زمان خالی ۱',
  et_slot_2: 'زمان خالی ۲',
  et_slots_registered: 'ثبت زمان‌های خالی ET',
  parent_process_code: 'کد فرایند والد',
  defense_date: 'تاریخ جلسه دفاع',
  defense_time: 'ساعت جلسه دفاع',
  reviewer_1_id: 'داور اول',
  reviewer_2_id: 'داور دوم',
  reviewer_1_name: 'نام داور اول',
  reviewer_2_name: 'نام داور دوم',
  psychotic_report_file: 'گزارش سایکوتیک',
  thesis_file: 'فایل پایان‌نامه',
  revised_thesis_file: 'پایان‌نامه اصلاح‌شده',
  all_conditions_met: 'احراز همه شروط',
  units_67_b_met: 'احراز ۶۷ واحد و معدل B',
  clinical_750_met: 'احراز ۷۵۰ ساعت بالینی',
  supervision_150_met: 'احراز ۱۵۰ ساعت سوپرویژن',
  therapy_250_met: 'احراز ۲۵۰ ساعت درمان',
  thesis_defense_eligibility_preview_fa: 'خلاصه شروط دفاع',
  permit_denial_reason: 'علت عدم مجوز دفاع',
  report_rejection_reason: 'علت رد گزارش',
  revision_notes: 'توضیحات اصلاح گزارش',
  therapy_changes_next_step_fa: 'گام پیشنهادی بعد از این فرایند',
  ui_completion_summary_fa: 'خلاصهٔ نتیجه (تعیین تکلیف هزینه جلسه)',
  fee_settlement_mode: 'نحوهٔ تسویهٔ مالی',
  fee_settlement_amount: 'مبلغ تسویه‌شده',
  reason: 'علت',
  termination_reason_code: 'کد علت قطع درمان',
  termination_note: 'توضیحات درمانگر',
  termination_reason_display: 'علت قطع (نمایشی)',
  termination_note_display: 'توضیحات درمانگر',
  nezarat_recommendation_fa: 'پیشنهاد کمیته نظارت',
  nezarat_recommendation_code: 'کد پیشنهاد نظارت',
  supervision_recommendation_display: 'پیشنهاد کمیته نظارت (نمایشی)',
  commission_opinion_fa: 'نظر کمیسیون تخصصی',
  commission_opinion_display: 'نظر کمیسیون (نمایشی)',
  commission_meeting_notes_fa: 'یادداشت جلسه کمیسیون',
  commission_result: 'نتیجه کمیسیون',
  education_verdict_notes_fa: 'یادداشت حکم کمیته آموزش',
  entry_source_display: 'منبع ورود به زیرفرایند',
  entry_reason: 'علت ورود',
  grandparent_process_code: 'فرایند مبدأ',
  photo: 'عکس پرسنلی',
  id_card: 'تصویر شناسنامه',
  national_card: 'تصویر کارت ملی',
  bachelor_degree: 'مدرک کارشناسی / پزشکی عمومی',
  master_degree: 'مدرک کارشناسی ارشد',
  latest_certificate: 'آخرین مدرک تحصیلی',
  digital_commitment: 'پذیرش قوانین انستیتو',
  selected_timeslot: 'زمان مصاحبه انتخاب‌شده',
  calendar_sla_deadline_at: 'مهلت تدوین تقویم آموزشی',
  fall_start_date: 'تاریخ شروع ترم پاییز',
  fall_end_date: 'تاریخ پایان ترم پاییز',
  winter_start_date: 'تاریخ شروع ترم زمستان',
  winter_end_date: 'تاریخ پایان ترم زمستان',
  fall_break_periods: 'دوره‌های تعطیلی ترم پاییز',
  winter_break_periods: 'دوره‌های تعطیلی ترم زمستان',
  registration_payment_window_start: 'شروع پنجره ثبت‌نام، پرداخت و شهریه',
  registration_payment_window_end: 'پایان پنجره ثبت‌نام، پرداخت و شهریه',
  intern_interview_deadline: 'مهلت مصاحبه انترن‌ها',
  teaching_assistant_interview_deadline: 'مهلت مصاحبه کمک‌مدرس',
  nowruz_holiday_start: 'شروع تعطیلات نوروز',
  nowruz_holiday_end: 'پایان تعطیلات نوروز',
  per_unit_cost_introductory: 'هزینه هر واحد دوره مقدماتی (ریال)',
  per_unit_cost_comprehensive: 'هزینه هر واحد دوره جامع (ریال)',
  interview_fee_introductory: 'هزینه مصاحبه دوره آشنایی (ریال)',
  interview_fee_comprehensive: 'هزینه مصاحبه دوره جامع (ریال)',
  license_status: 'وضعیت پروانه',
  new_license_number: 'شماره پروانه جدید',
  license_notes: 'توضیحات پروانه',
  winter_license_notes: 'توضیحات پروانه (ترم زمستان)',
  courses_fall: 'جدول دروس ترم پاییز',
  courses_winter: 'جدول دروس ترم زمستان',
  courses: 'جدول دروس ترم',
  courses_finalized_fall: 'جدول نهایی دروس ترم پاییز',
  courses_finalized_winter: 'جدول نهایی دروس ترم زمستان',
  courses_finalized: 'جدول نهایی دروس',
  marketing_info_sent_to_manager: 'ارسال اطلاعات کمپین به مدیر مارکتینگ',
  marketing_notes: 'یادداشت انتقال به مدیر مارکتینگ',
  comprehensive_interviewers: 'مصاحبه‌کنندگان دوره جامع',
  comprehensive_date_range_start: 'شروع بازه مصاحبه دوره جامع',
  comprehensive_date_range_end: 'پایان بازه مصاحبه دوره جامع',
  introductory_interviewers: 'مصاحبه‌کنندگان دوره مقدماتی',
  introductory_date_range_start: 'شروع بازه مصاحبه دوره مقدماتی',
  introductory_date_range_end: 'پایان بازه مصاحبه دوره مقدماتی',
  interview_start_time: 'ساعت شروع مصاحبه‌ها',
  interview_end_time: 'ساعت پایان مصاحبه‌ها',
  slot_duration_minutes: 'مدت هر نوبت مصاحبه (دقیقه)',
  interview_mode: 'نوع مصاحبه',
  interview_location_or_link: 'محل یا لینک مصاحبه',
  classroom_location: 'محل برگزاری کلاس',
  instructor_coordinated: 'هماهنگی با مدرس انجام شد',
  proposed_day: 'روز پیشنهادی',
  proposed_time: 'ساعت پیشنهادی',
  prep_term_label_fa: 'ترم آماده‌سازی',
  pause_start_date: 'تاریخ شروع وقفه',
  pause_end_date: 'تاریخ پایان وقفه',
  pause_days: 'طول وقفه (روز)',
  requested_pause_range: 'بازه زمانی وقفه درخواستی',
  meeting_date: 'تاریخ جلسه بررسی',
  meeting_link: 'لینک جلسه آنلاین',
  meeting_location_fa: 'محل برگزاری جلسه',
  path: 'مسیر درخواست (تغییر/اضافه رسته)',
  new_tracks: 'رسته(های) جدید',
  current_tracks: 'رسته(های) فعلی',
  applied_tracks: 'رسته(های) اعمال‌شده',
  ta_name_fa: 'نام کمک‌مدرس',
  meeting_time: 'ساعت جلسه بررسی',
  meeting_type: 'نوع برگزاری جلسه',
  rejection_explanation: 'توضیحات رد درخواست',
  committee_notes: 'یادداشت‌های کمیته',
  essay_word: 'فایل Word جستار',
  essay_pdf: 'فایل PDF جستار',
  edited_essay_word: 'فایل Word نهایی (مرکز مرجع)',
  selected_minutes_note: 'یادداشت دقایق منتخب',
  refined_minutes_from_to: 'بازهٔ دقایق مهم',
  publish_platforms: 'پلتفرم‌های انتشار',
  instructor_name: 'نام مدرس',
  session_date: 'تاریخ جلسه کلاس',
  class_session_date: 'تاریخ جلسه کلاس',
  class_session_number: 'شماره جلسه کلاس',
  upload_deadline_at: 'مهلت آپلود سوالات',
  review_deadline_at: 'مهلت بررسی مدرس',
  revision_deadline_at: 'مهلت اصلاح سوالات',
  upload_late_violation_reported: 'گزارش تخلف تأخیر آپلود',
  conceptual_questions_score_total: 'نمرهٔ تجمیعی سوالات تستی‌مفهومی (ترم)',
  ta_conceptual_score_total: 'نمرهٔ تجمیعی سوالات تستی‌مفهومی',
  session_score_awarded: 'نمرهٔ این جلسه (طراحی سوال)',
  question_1_status: 'وضعیت سوال ۱',
  question_2_status: 'وضعیت سوال ۲',
  question_3_status: 'وضعیت سوال ۳',
  question_1_rejection_note: 'توضیح رد سوال ۱',
  question_2_rejection_note: 'توضیح رد سوال ۲',
  question_3_rejection_note: 'توضیح رد سوال ۳',
  ta_upload_entered_at: 'زمان ورود به مرحلهٔ آپلود',
  instructor_review_entered_at: 'زمان ورود به بررسی مدرس',
  question_rejected_entered_at: 'زمان ورود به اصلاح',
  course_track: 'رستهٔ درس',
  course_code: 'کد درس',
  students_attendance: 'لیست حضور و غیاب جلسه',
  attendance_summary: 'خلاصهٔ ثبت حضور',
  live_supervision_attendance_summary: 'خلاصهٔ حضور سوپرویژن زنده',
  student_absence_count: 'تعداد غیبت دانشجو در درس',
  article_violation_pending: 'گزارش تخلف مقاله‌نویسی معوق',
  report_grade: 'نمره گزارش پایانی',
  final_report_pdf: 'گزارش پایانی PDF',
  final_report_uploaded_at: 'زمان آپلود گزارش پایانی',
  pass_fail: 'وضعیت قبولی (PASS/FAIL)',
  borderline_status: 'وضعیت نمره مرزی',
  borderline_pending: 'نمره مرزی (۶۴–۷۳)',
  retake_eligible: 'واجد شرایط امتحان مجدد',
  exam_pack_id: 'پک آزمون نهایی',
  retake_exam_pack_id: 'پک امتحان مجدد',
  test_score: 'نمره آزمون تستی',
  session_18_submitted_at: 'زمان ثبت جلسه ۱۸',
}

const INTERVIEW_RESULT_LABELS = {
  conditional_therapy: 'درمان شرطی',
  single_course: 'تک‌درس / محدود',
  full_admission: 'پذیرش کامل',
  rejected: 'رد',
}

/** مقادیر رشته‌ای رایج در context که در متادیتای مرحله‌ها نیستند */
export const CONTEXT_VALUE_LABELS = {
  cash: 'نقدی',
  installment: 'اقساطی',
  full: 'ثبت‌نام/پرداخت کامل',
  PASS: 'قبول',
  FAIL: 'مردود',
  pass: 'قبول',
  fail: 'مردود',
  pending: 'در انتظار',
  completed: 'تکمیل‌شده',
  cancelled: 'لغو شده',
  approved: 'تایید شده',
  rejected: 'رد شده',
  therapy_interruption_long: 'وقفهٔ طولانی درمان',
  supervision_interruption_long: 'وقفهٔ طولانی سوپرویژن',
  supervision_interruption_no_return: 'عدم بازگشت پس از وقفهٔ سوپرویژن',
  supervision_interruption_rejected: 'رد درخواست وقفهٔ سوپرویژن',
  after_start_therapy_complete: 'پس از تکمیل آغاز درمان',
  theory_1: 'درس تئوری ۱',
  theory_2: 'درس تئوری ۲',
  online: 'آنلاین',
  in_person: 'حضوری',
}

/**
 * @param {unknown[]} forms
 * @returns {Map<string, string>}
 */
export function buildFieldLabelMap(forms) {
  const m = new Map()
  for (const f of forms || []) {
    for (const field of f.fields || []) {
      const name = field.name
      if (name && field.label_fa) m.set(name, field.label_fa)
    }
  }
  return m
}

export function prettyKeyFallback(key) {
  if (key.startsWith('__')) return null
  if (CONTEXT_KEY_LABELS[key]) return CONTEXT_KEY_LABELS[key]
  return key.replace(/_/g, ' ')
}

/**
 * @param {string} key
 * @param {Map<string, string>|null|undefined} fieldLabelMap
 */
export function resolveContextRowLabel(key, fieldLabelMap) {
  if (CONTEXT_KEY_LABELS[key]) return CONTEXT_KEY_LABELS[key]
  if (fieldLabelMap && fieldLabelMap.has(key)) return fieldLabelMap.get(key)
  return prettyKeyFallback(key)
}

function formatIsoMaybe(s) {
  if (typeof s !== 'string') return s
  const t = Date.parse(s)
  if (Number.isNaN(t)) return s
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(s.slice(0, 10)) && !s.includes('T')
  return formatShamsiTehran(s, { dateOnly })
}

function looksLikeIso(s) {
  return typeof s === 'string' && (/^\d{4}-\d{2}-\d{2}/.test(s) || (s.includes('T') && s.includes(':')))
}

/** رشتهٔ تک‌مقدار در context: تاریخ، یا برچسب فارسی از CONTEXT_VALUE_LABELS */
export function formatContextStringForDisplay(value) {
  if (typeof value !== 'string') return null
  if (looksLikeIso(value)) return formatIsoMaybe(value)
  if (CONTEXT_VALUE_LABELS[value]) return CONTEXT_VALUE_LABELS[value]
  return null
}

export function formatInterviewResultDisplay(value, labelState) {
  if (typeof value !== 'string') return null
  return INTERVIEW_RESULT_LABELS[value] || (labelState ? labelState(value) : value)
}

const MAX_DEPTH = 5

/**
 * اگر مقدار شبیه خروجی فیلد file_upload باشد، پیش‌نمایش تصویر/PDF در پنل ادمین/کارمند.
 * @param {typeof import('react')} React
 * @returns {import('react').ReactNode | null}
 */
function renderIfProcessStepFileUpload(React, value) {
  const { url, mime, isLocalPlaceholder, fileName } = parseStepFileUploadValue(value)
  if (url) {
    const src = resolveUploadPublicUrl(url)
    const showImage = mime.startsWith('image/')
    const showPdf = mime === 'application/pdf'
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', alignItems: 'flex-start' }}>
        {showImage && (
          <a href={src} target="_blank" rel="noopener noreferrer">
            <img
              src={src}
              alt=""
              style={{
                maxWidth: 'min(100%, 280px)',
                maxHeight: '200px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                display: 'block',
                objectFit: 'contain',
              }}
            />
          </a>
        )}
        {showPdf && (
          <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline">
            باز کردن PDF
          </a>
        )}
        {!showImage && !showPdf && (
          <a href={src} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline">
            باز کردن فایل
          </a>
        )}
        <span style={{ fontSize: '0.72rem', color: '#64748b', direction: 'ltr', wordBreak: 'break-all' }}>{url}</span>
      </div>
    )
  }
  if (isLocalPlaceholder) {
    return (
      <span style={{ color: '#b45309', fontSize: '0.82rem' }}>
        فایل روی سرور ثبت نشده (نام محلی: {fileName || '—'})
      </span>
    )
  }
  return null
}

/**
 * @param {typeof import('react')} React
 * @param {Map<string, string>|null|undefined} fieldLabelMap
 * @param {(s: string) => string} labelState
 */
export function renderFriendlyContextValue(React, value, fieldLabelMap, labelState, depth = 0) {
  if (depth > MAX_DEPTH) return '…'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') {
    const asDisplay = formatContextStringForDisplay(value)
    if (asDisplay !== null) return asDisplay
    const fileFromString = renderIfProcessStepFileUpload(React, value)
    if (fileFromString !== null) return fileFromString
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '—'
    const allPrimitive = value.every(x => x === null || x === undefined
      || typeof x === 'string' || typeof x === 'number' || typeof x === 'boolean')
    if (allPrimitive) {
      return value.map(x => (x === null || x === undefined ? '—' : String(x))).join('، ')
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
        {value.map((item, i) => (
          <div
            key={i}
            style={{
              padding: '0.45rem 0.55rem',
              background: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              fontSize: '0.8rem',
            }}
          >
            {renderFriendlyContextValue(React, item, fieldLabelMap, labelState, depth + 1)}
          </div>
        ))}
      </div>
    )
  }
  if (typeof value === 'object') {
    const filePreview = renderIfProcessStepFileUpload(React, value)
    if (filePreview !== null) return filePreview
    const entries = Object.entries(value)
    if (entries.length === 0) return '—'
    return (
      <div style={{ paddingRight: depth ? '0.35rem' : 0 }}>
        {entries.map(([k, v]) => {
          const subLabel = resolveContextRowLabel(k, fieldLabelMap) || k
          return (
            <div
              key={k}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(88px, 32%) 1fr',
                gap: '0.4rem',
                fontSize: depth ? '0.78rem' : '0.82rem',
                marginBottom: '0.35rem',
                alignItems: 'start',
              }}
            >
              <span style={{ color: '#6b7280', fontWeight: 600 }}>{subLabel}</span>
              <span style={{ color: '#111827', lineHeight: 1.5 }}>
                {renderFriendlyContextValue(React, v, fieldLabelMap, labelState, depth + 1)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }
  return String(value)
}
