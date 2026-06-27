/**
 * فرایندهای سطح مؤسسه (institute-level) که وابسته به «نوع دورهٔ» دانشجو نیستند.
 * آماده‌سازی ترم پاییز/زمستان برای هر دو دورهٔ جامع و آشنایی اجرا می‌شود.
 */
export const SEMESTER_PREP_PROCESSES = new Set([
  'fall_semester_preparation',
  'winter_semester_preparation',
])

/** فرایندهای مستقل از نوع دوره (انتخابگر نوع دوره برایشان معنا ندارد). */
export const INSTITUTE_PROCESS_CODES = new Set([...SEMESTER_PREP_PROCESSES])

/** @param {string | null | undefined} processCode */
export function isInstituteLevelProcess(processCode) {
  if (!processCode) return false
  return INSTITUTE_PROCESS_CODES.has(processCode)
}
