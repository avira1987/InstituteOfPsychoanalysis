/** کدام بخش‌های اسنپ‌شات ثبت‌شدهٔ آماده‌سازی روی هاب نشان داده شوند. */

export const RECORDED_SECTION_ORDER = [
  'calendar',
  'tuition',
  'license',
  'courses',
  'marketing',
  'interviews',
]

export const CALENDAR_FIELD_ROWS = [
  ['fall_start_date', 'شروع ترم پاییز'],
  ['fall_end_date', 'پایان ترم پاییز'],
  ['winter_start_date', 'شروع ترم زمستان'],
  ['winter_end_date', 'پایان ترم زمستان'],
  ['registration_payment_window_start', 'شروع پنجره ثبت‌نام'],
  ['registration_payment_window_end', 'پایان پنجره ثبت‌نام'],
  ['intern_interview_deadline_start', 'شروع بازه مصاحبه انترن‌ها'],
  ['intern_interview_deadline_end', 'پایان بازه مصاحبه انترن‌ها'],
  ['teaching_assistant_interview_deadline_start', 'شروع بازه مصاحبه کمک‌مدرس'],
  ['teaching_assistant_interview_deadline_end', 'پایان بازه مصاحبه کمک‌مدرس'],
  ['nowruz_holiday_start', 'شروع تعطیلات نوروز'],
  ['nowruz_holiday_end', 'پایان تعطیلات نوروز'],
]

export const TUITION_FIELD_ROWS = [
  ['per_unit_cost_introductory', 'واحد آشنایی'],
  ['per_unit_cost_comprehensive', 'واحد جامع'],
  ['interview_fee_introductory', 'مصاحبه آشنایی'],
  ['interview_fee_comprehensive', 'مصاحبه جامع'],
  ['registration_interview_fee_rial', 'مصاحبه ثبت‌نام (پشتیبان)'],
  ['start_therapy_first_session_fee_rial', 'اولین جلسه درمان'],
  ['extra_session_fee_rial', 'جلسه اضافه درمان'],
  ['default_therapy_session_fee_toman', 'جلسه درمان آموزشی (تومان)'],
]

export const LICENSE_FIELD_ROWS = [
  ['license_status', 'وضعیت پروانه'],
  ['current_license_number', 'شماره پروانه فعلی'],
  ['new_license_number', 'شماره پروانه جدید'],
  ['license_notes', 'توضیحات'],
  ['winter_license_notes', 'توضیحات (زمستان)'],
]

const DRAFT_COURSE_COLUMNS = [
  ['course_name', 'نام درس'],
  ['track', 'رسته'],
  ['units', 'واحد'],
  ['proposed_day', 'روز پیشنهادی'],
  ['proposed_time', 'ساعت پیشنهادی'],
  ['instructor', 'مدرس'],
  ['teaching_assistant', 'کمک‌مدرس'],
]

const FINAL_COURSE_COLUMNS = [
  ['course_name', 'نام درس'],
  ['track', 'رسته'],
  ['units', 'واحد'],
  ['day', 'روز'],
  ['time', 'ساعت'],
  ['instructor', 'مدرس'],
  ['teaching_assistant', 'کمک‌مدرس'],
  ['classroom_location', 'مکان کلاس'],
  ['instructor_coordinated', 'هماهنگی با مدرس'],
]

export const COURSE_TABLE_DEFS = [
  { key: 'courses_fall', label: 'لیست دروس ترم پاییز', columns: DRAFT_COURSE_COLUMNS },
  { key: 'courses_winter', label: 'لیست دروس ترم زمستان', columns: DRAFT_COURSE_COLUMNS },
  { key: 'courses', label: 'لیست دروس', columns: DRAFT_COURSE_COLUMNS },
  { key: 'courses_finalized_fall', label: 'برنامه نهایی ترم پاییز', columns: FINAL_COURSE_COLUMNS },
  { key: 'courses_finalized_winter', label: 'برنامه نهایی ترم زمستان', columns: FINAL_COURSE_COLUMNS },
  { key: 'courses_finalized', label: 'برنامه نهایی دروس', columns: FINAL_COURSE_COLUMNS },
]

export const MARKETING_FIELD_ROWS = [
  ['marketing_info_sent_to_manager', 'ارسال به مدیر مارکتینگ'],
  ['marketing_notes', 'یادداشت انتقال'],
]

export const INTERVIEW_FIELD_ROWS = [
  ['comprehensive_interviewers', 'مصاحبه‌کنندگان دوره جامع'],
  ['comprehensive_date_range_start', 'شروع بازه مصاحبه جامع'],
  ['comprehensive_date_range_end', 'پایان بازه مصاحبه جامع'],
  ['introductory_interviewers', 'مصاحبه‌کنندگان دوره آشنایی'],
  ['introductory_date_range_start', 'شروع بازه مصاحبه آشنایی'],
  ['introductory_date_range_end', 'پایان بازه مصاحبه آشنایی'],
  ['interview_mode', 'نوع مصاحبه'],
  ['interview_location_fa', 'محل برگزاری'],
  ['interview_location_or_link', 'محل یا لینک'],
  ['interview_start_time', 'ساعت شروع'],
  ['interview_end_time', 'ساعت پایان'],
  ['slot_duration_minutes', 'مدت هر نوبت (دقیقه)'],
]

export const INTERVIEW_COURSE_LABELS_FA = {
  comprehensive: 'دوره جامع',
  introductory: 'دوره آشنایی',
}

export function recordedValuePresent(value) {
  if (value == null) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (typeof value === 'boolean' || typeof value === 'number') return true
  if (Array.isArray(value)) return value.some(recordedValuePresent)
  if (typeof value === 'object') {
    return Object.entries(value).some(
      ([key, item]) => !String(key).startsWith('__') && recordedValuePresent(item),
    )
  }
  return false
}

export function recordedSectionKeys(recorded) {
  const data = recorded && typeof recorded === 'object' ? recorded : {}
  return RECORDED_SECTION_ORDER.filter((key) => recordedValuePresent(data[key]))
}

export function hasRecordedPrepData(recorded) {
  return recordedSectionKeys(recorded).length > 0
}

export function shouldShowPrepRecordedSummary(entry) {
  if (!entry || typeof entry !== 'object') return false
  return Boolean(entry.active || entry.instance_id || entry.completed_instance_id)
}

export function visibleCourseTables(courses) {
  const tables = courses && typeof courses === 'object' ? courses : {}
  return COURSE_TABLE_DEFS.filter((def) => Array.isArray(tables[def.key]) && tables[def.key].length > 0)
}

export function interviewPlanGroups(plan) {
  if (!plan || typeof plan !== 'object') return []
  return ['comprehensive', 'introductory']
    .filter((key) => recordedValuePresent(plan[key]))
    .map((key) => ({ key, label: INTERVIEW_COURSE_LABELS_FA[key], group: plan[key] }))
}
