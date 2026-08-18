import { userHasAnyRole } from './userRoles.js'
import { OVERRIDE_ROLES } from './processRollbackUtils.js'

/** نقش‌های پرسنل مجاز به ریست — هم‌نام بک‌اند (override). */
export const RESTART_STAFF_ROLES = OVERRIDE_ROLES

/** فرایندهای غیرقابل ریست — هم‌تراز app/meta/process_restart_policy.py */
export const RESTART_BLOCKED_PROCESS_CODES = new Set([
  'fee_determination',
  'session_payment',
])

export function isProcessRestartBlocked(processCode) {
  if (!processCode) return true
  return RESTART_BLOCKED_PROCESS_CODES.has(processCode)
}

export function studentRestartReasonRequired(user) {
  return user?.role === 'student'
}

/** دلیل برای پرسنل override و دانشجو الزامی است. */
export function restartReasonRequired(user) {
  if (studentRestartReasonRequired(user)) return true
  return userHasAnyRole(user, OVERRIDE_ROLES)
}

/**
 * آیا بخش «شروع دوباره از ابتدا» نمایش داده شود؟
 * پرسنل: فقط مدیر / معاون. دانشجو: برای هر نقش student (مالکیت در API).
 */
export function canShowProcessRestart(instanceDetail, user) {
  if (!instanceDetail || !user?.role) return false
  if (instanceDetail.is_cancelled) return false
  if (isProcessRestartBlocked(instanceDetail.process_code)) return false

  if (userHasAnyRole(user, OVERRIDE_ROLES)) return true
  if (user.role === 'student') return true
  return false
}
