/**
 * فرایندهای سطح مؤسسه (institute-level) که وابسته به «نوع دورهٔ» دانشجو نیستند.
 * آماده‌سازی ترم پاییز/زمستان برای هر دو دورهٔ جامع و آشنایی اجرا می‌شود.
 */
import { INSTITUTE_START_CODES, isInstituteStartProcess } from './processStartScope'

export const SEMESTER_PREP_PROCESSES = INSTITUTE_START_CODES

/** فرایندهای مستقل از نوع دوره (انتخابگر نوع دوره برایشان معنا ندارد). */
export const INSTITUTE_PROCESS_CODES = INSTITUTE_START_CODES

/** @param {string | null | undefined} processCode */
export function isInstituteLevelProcess(processCode) {
  return isInstituteStartProcess(processCode)
}
