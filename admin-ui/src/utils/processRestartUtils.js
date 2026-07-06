/** نقش‌های پرسنل مجاز به ریست (هم‌نام با بک‌اند). */
export const RESTART_STAFF_ROLES = ['admin', 'deputy_education', 'staff']

/** فرایندهای غیرقابل ریست — هم‌تراز app/meta/process_restart_policy.py */
export const RESTART_BLOCKED_PROCESS_CODES = new Set([
  'fee_determination',
  'session_payment',
  'fall_semester_preparation',
  'winter_semester_preparation',
])

export function isProcessRestartBlocked(processCode) {
  if (!processCode) return true
  return RESTART_BLOCKED_PROCESS_CODES.has(processCode)
}

export function studentRestartReasonRequired(user) {
  return user?.role === 'student'
}

/**
 * آیا بخش «شروع دوباره از ابتدا» نمایش داده شود؟
 * @param {object} instanceDetail
 * @param {object} user
 */
export function canShowProcessRestart(instanceDetail, user) {
  if (!instanceDetail || !user?.role) return false
  if (instanceDetail.is_cancelled) return false
  if (isProcessRestartBlocked(instanceDetail.process_code)) return false

  const role = user.role
  if (RESTART_STAFF_ROLES.includes(role)) return true
  if (role === 'student') return true
  return false
}
