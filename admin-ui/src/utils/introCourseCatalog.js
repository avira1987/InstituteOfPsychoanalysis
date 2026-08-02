/**
 * نمایش برچسب دروس از context منتشرشده (بدون کاتالوگ ثابت).
 */

export function formatCourseCodesDisplay(codes, labels = {}) {
  const list = Array.isArray(codes) ? codes : []
  if (!list.length) return ''
  const map = labels && typeof labels === 'object' ? labels : {}
  return list.map((c) => map[c] || c).join('، ')
}

/** گزینه‌های درس از context نمونه فرایند (خروجی آماده‌سازی ترم). */
export function optionsFromContext(contextData) {
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}
  const raw = ctx.available_course_options
  if (Array.isArray(raw) && raw.length) {
    return raw.map((o) => ({
      value: String(o.value),
      label_fa: o.label_fa || String(o.value),
      day: o.day,
      time_text: o.time_text,
      classroom_location: o.classroom_location,
      instructor_name: o.instructor_name,
    }))
  }
  const codes = ctx.available_courses || ctx.lms?.available_courses || []
  const labelMap = ctx.course_labels || {}
  if (Array.isArray(codes) && codes.length) {
    return codes.map((c) => ({
      value: String(c),
      label_fa: labelMap[c] || String(c),
    }))
  }
  return []
}

export const NO_OFFERINGS_HINT_FA =
  'لیست دروس این ترم هنوز از فرایند آماده‌سازی ترم منتشر نشده است؛ پس از انتشار توسط انستیتو این بخش فعال می‌شود.'
