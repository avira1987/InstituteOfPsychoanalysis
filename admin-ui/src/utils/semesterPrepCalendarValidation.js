import { isoDateToShamsiParts } from './shamsiDateTime'

/** فیلدهای تاریخ فرم تقویم — هم‌تراز backend SEMESTER_PREP_CALENDAR_DATE_FIELDS */
export const SEMESTER_PREP_CALENDAR_DATE_FIELDS = [
  'fall_start_date',
  'fall_end_date',
  'winter_start_date',
  'winter_end_date',
  'registration_payment_window_start',
  'registration_payment_window_end',
  'intern_interview_deadline_start',
  'intern_interview_deadline_end',
  'teaching_assistant_interview_deadline_start',
  'teaching_assistant_interview_deadline_end',
  'nowruz_holiday_start',
  'nowruz_holiday_end',
]

export const SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS = [
  'fall_break_periods',
  'winter_break_periods',
]

const FIELD_LABELS_FA = {
  fall_start_date: 'تاریخ شروع ترم پاییز',
  fall_end_date: 'تاریخ پایان ترم پاییز',
  winter_start_date: 'تاریخ شروع ترم زمستان',
  winter_end_date: 'تاریخ پایان ترم زمستان',
  registration_payment_window_start: 'شروع پنجره ثبت‌نام',
  registration_payment_window_end: 'پایان پنجره ثبت‌نام',
  intern_interview_deadline_start: 'شروع بازه مصاحبه انترن‌ها',
  intern_interview_deadline_end: 'پایان بازه مصاحبه انترن‌ها',
  teaching_assistant_interview_deadline_start: 'شروع بازه مصاحبه کمک مدرسی',
  teaching_assistant_interview_deadline_end: 'پایان بازه مصاحبه کمک مدرسی',
  nowruz_holiday_start: 'شروع تعطیلات نوروز',
  nowruz_holiday_end: 'پایان تعطیلات نوروز',
  fall_break_periods: 'دوره‌های تعطیلی ترم پاییز',
  winter_break_periods: 'دوره‌های تعطیلی ترم زمستان',
}

const YEAR_OFFSET_MIN = -1
const YEAR_OFFSET_MAX = 1

/** @returns {{ jy: number }} */
export function currentShamsiYearParts() {
  const now = isoDateToShamsiParts(new Date().toISOString().slice(0, 10))
  return { jy: now?.jy ?? 1403 }
}

/** @returns {{ minJy: number, maxJy: number }} */
export function semesterPrepCalendarShamsiYearBounds() {
  const { jy } = currentShamsiYearParts()
  return { minJy: jy + YEAR_OFFSET_MIN, maxJy: jy + YEAR_OFFSET_MAX }
}

export function isSemesterPrepCalendarDateField(fieldName) {
  return (
    SEMESTER_PREP_CALENDAR_DATE_FIELDS.includes(fieldName)
    || SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS.includes(fieldName)
  )
}

/**
 * @param {object} values
 * @returns {{ field: string, message: string }[]}
 */
export function validateSemesterPrepCalendarDates(values) {
  const vals = values || {}
  const { minJy, maxJy } = semesterPrepCalendarShamsiYearBounds()
  const errors = []

  const pushYearError = (field, jy) => {
    const label = FIELD_LABELS_FA[field] || field
    errors.push({
      field,
      message: `«${label}» (سال ${jy}) خارج از بازهٔ مجاز سال شمسی ${minJy} تا ${maxJy} نسبت به سال جاری است.`,
    })
  }

  for (const key of SEMESTER_PREP_CALENDAR_DATE_FIELDS) {
    const raw = vals[key]
    if (!raw) continue
    const parts = isoDateToShamsiParts(raw)
    if (!parts) continue
    if (parts.jy < minJy || parts.jy > maxJy) pushYearError(key, parts.jy)
  }

  for (const listKey of SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS) {
    const ranges = Array.isArray(vals[listKey]) ? vals[listKey] : []
    ranges.forEach((row, i) => {
      if (!row || typeof row !== 'object') return
      for (const partKey of ['start', 'end']) {
        const raw = row[partKey]
        if (!raw) continue
        const parts = isoDateToShamsiParts(raw)
        if (!parts) continue
        if (parts.jy < minJy || parts.jy > maxJy) {
          const label = FIELD_LABELS_FA[listKey] || listKey
          errors.push({
            field: listKey,
            message: `«${label}» — بازه ${i + 1}: سال ${parts.jy} خارج از بازهٔ مجاز ${minJy} تا ${maxJy} است.`,
          })
        }
      }
      const start = row.start
      const end = row.end
      if (start && end && String(end) <= String(start)) {
        const label = FIELD_LABELS_FA[listKey] || listKey
        errors.push({
          field: listKey,
          message: `«${label}» — بازه ${i + 1}: تاریخ پایان باید بعد از شروع باشد.`,
        })
      }
    })
  }

  const checkOrder = (startKey, endKey, message) => {
    const start = vals[startKey]
    const end = vals[endKey]
    if (start && end && String(end) < String(start)) {
      errors.push({ field: endKey, message })
    }
  }

  checkOrder('fall_start_date', 'fall_end_date', 'تاریخ پایان ترم پاییز نمی‌تواند قبل از شروع باشد.')
  checkOrder('winter_start_date', 'winter_end_date', 'تاریخ پایان ترم زمستان نمی‌تواند قبل از شروع باشد.')
  checkOrder(
    'registration_payment_window_start',
    'registration_payment_window_end',
    'پایان پنجره ثبت‌نام نمی‌تواند قبل از شروع باشد.',
  )
  checkOrder(
    'intern_interview_deadline_start',
    'intern_interview_deadline_end',
    'پایان بازه مصاحبه انترن‌ها نمی‌تواند قبل از شروع باشد.',
  )
  checkOrder(
    'teaching_assistant_interview_deadline_start',
    'teaching_assistant_interview_deadline_end',
    'پایان بازه مصاحبه کمک مدرسی نمی‌تواند قبل از شروع باشد.',
  )
  checkOrder('nowruz_holiday_start', 'nowruz_holiday_end', 'پایان تعطیلات نوروز نمی‌تواند قبل از شروع باشد.')

  const fallEnd = vals.fall_end_date
  const winterStart = vals.winter_start_date
  if (fallEnd && winterStart && String(winterStart) < String(fallEnd)) {
    errors.push({
      field: 'winter_start_date',
      message: 'شروع ترم زمستان نمی‌تواند قبل از پایان ترم پاییز باشد.',
    })
  }

  return errors
}

export function contextHasOutlierCalendarDates(context) {
  return validateSemesterPrepCalendarDates(context || {}).length > 0
}
