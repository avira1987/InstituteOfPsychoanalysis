/**
 * دامنهٔ شروع دستی فرایند — هم‌تراز app/meta/process_start_scope.py
 */

export const INSTITUTE_START_CODES = new Set([
  'fall_semester_preparation',
  'winter_semester_preparation',
])

export const STAFF_START_CODES = new Set([
  'class_session_cancellation',
  'live_supervision_session_prep',
  'live_therapy_observation_session_prep',
  'class_attendance',
])

/**
 * @param {string | null | undefined} processCode
 * @returns {'student' | 'staff' | 'institute'}
 */
export function getManualStartScope(processCode) {
  const code = (processCode || '').trim()
  if (INSTITUTE_START_CODES.has(code)) return 'institute'
  if (STAFF_START_CODES.has(code)) return 'staff'
  return 'student'
}

/** @param {string | null | undefined} processCode */
export function isInstituteStartProcess(processCode) {
  return getManualStartScope(processCode) === 'institute'
}

/** @param {string | null | undefined} processCode */
export function isStaffStartProcess(processCode) {
  return getManualStartScope(processCode) === 'staff'
}
