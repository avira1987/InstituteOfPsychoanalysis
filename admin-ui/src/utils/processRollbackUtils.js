/** نقش‌هایی که API بازگشت مرحله را اجازه می‌دهد (هم‌نام با بک‌اند). */
export const ROLLBACK_ROLES = ['admin', 'deputy_education', 'staff']

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
  if (!user?.role || !ROLLBACK_ROLES.includes(user.role)) return false
  const h = instanceDetail.history || []
  if (h.length < 2) return false
  return !!resolveRollbackTargetFromHistory(h, instanceDetail.current_state)
}

export function previousStateFromHistory(instanceDetail) {
  const h = instanceDetail.history || []
  return resolveRollbackTargetFromHistory(h, instanceDetail?.current_state)
}
