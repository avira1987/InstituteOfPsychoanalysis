/** مراحلی که نقش کمیته دروس (اجرایی/علمی) در آن مسئول است. */
export const COMMITTEE_PREP_STATES = new Set([
  'calendar_entry',
  'course_list_creation',
  'course_finalization',
  'course_list_review',
])

const PREP_CODES = ['fall_semester_preparation', 'winter_semester_preparation']

/**
 * @param {Record<string, { active?: boolean, current_state?: string }> | null | undefined} processes
 * @returns {{ code: string, entry: object } | null}
 */
export function pickActiveSemesterPrep(processes) {
  for (const code of PREP_CODES) {
    const entry = processes?.[code]
    if (entry?.active && COMMITTEE_PREP_STATES.has(entry.current_state)) {
      return { code, entry }
    }
  }
  for (const code of PREP_CODES) {
    const entry = processes?.[code]
    if (entry?.active) return { code, entry }
  }
  return null
}

/**
 * لینک workbench هوشمند: زمستان فعال → زمستان؛ پاییز فعال → پاییز؛ در غیر این صورت هاب.
 * @param {Record<string, { active?: boolean }> | null | undefined} processes
 * @returns {string}
 */
export function resolveSemesterPrepWorkbenchHref(processes) {
  const winter = processes?.winter_semester_preparation
  if (winter?.active) {
    return '/panel/semester-prep/workbench?process_code=winter_semester_preparation'
  }
  const fall = processes?.fall_semester_preparation
  if (fall?.active) {
    return '/panel/semester-prep/workbench?process_code=fall_semester_preparation'
  }
  return '/panel/semester-prep'
}
