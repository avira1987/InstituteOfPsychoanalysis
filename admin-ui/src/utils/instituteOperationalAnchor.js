/**
 * Institute operational anchor (INST-OPS) — system record for semester-prep workflows.
 * Not a real student; belongs on /panel/semester-prep, not the student tracker list.
 */

export const INSTITUTE_OPS_DEFAULT_CODE = 'INST-OPS'

export const INSTITUTE_OPS_LABEL_FA = 'پرونده عملیاتی انستیتو'

/**
 * @param {{ student_code?: string, extra_data?: Record<string, unknown> } | null | undefined} student
 * @param {string} [opsCode]
 */
export function isInstituteOperationalStudent(student, opsCode = INSTITUTE_OPS_DEFAULT_CODE) {
  if (!student) return false
  const code = (opsCode || INSTITUTE_OPS_DEFAULT_CODE).trim()
  if ((student.student_code || '').trim() === code) return true
  const extra = student.extra_data
  return !!(extra && typeof extra === 'object' && extra.institute_operational_anchor)
}
