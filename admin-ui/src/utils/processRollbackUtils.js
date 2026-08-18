import { userHasAnyRole } from './userRoles.js'

/** نقش‌های مجاز به بازگشت مرحله (هم‌نام با app/meta/process_override_policy.py). */
export const OVERRIDE_ROLES = ['admin', 'deputy_education', 'deputy_education_director']

/** @deprecated از OVERRIDE_ROLES استفاده کنید */
export const ROLLBACK_ROLES = OVERRIDE_ROLES

/**
 * مرحلهٔ عملیاتی قبلی — manual_rollback را نادیده می‌گیرد تا بازگشت زنجیره‌ای درست کار کند.
 * (هم‌منطق با app/meta/process_rollback.py)
 */
export function resolveRollbackTargetFromHistory(history, currentState) {
  if (!currentState || !history?.length) return null
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i]
    if (entry.to_state !== currentState) continue
    if (entry.trigger_event === 'manual_rollback') continue
    if (!entry.from_state) return null
    return entry.from_state
  }
  return null
}

export function canShowProcessRollback(instanceDetail, user) {
  if (!instanceDetail || instanceDetail.is_cancelled) return false
  if (!userHasAnyRole(user, OVERRIDE_ROLES)) return false
  const h = instanceDetail.history || []
  if (h.length < 2) return false
  return !!resolveRollbackTargetFromHistory(h, instanceDetail.current_state)
}

export function previousStateFromHistory(instanceDetail) {
  const h = instanceDetail.history || []
  return resolveRollbackTargetFromHistory(h, instanceDetail?.current_state)
}

/** دلیل بازگشت برای نقش‌های override الزامی است. */
export function rollbackReasonRequired(user) {
  return userHasAnyRole(user, OVERRIDE_ROLES)
}
