/** نقش‌هایی که API بازگشت مرحله را اجازه می‌دهد (هم‌نام با بک‌اند). */
export const ROLLBACK_ROLES = ['admin', 'deputy_education', 'staff']

export function canShowProcessRollback(instanceDetail, user) {
  if (!instanceDetail || instanceDetail.is_cancelled) return false
  if (!user?.role || !ROLLBACK_ROLES.includes(user.role)) return false
  const h = instanceDetail.history || []
  if (h.length < 2) return false
  const last = h[h.length - 1]
  if (last.from_state == null || last.from_state === '') return false
  const cur = instanceDetail.current_state
  if (last.to_state !== cur) return false
  return true
}

export function previousStateFromHistory(instanceDetail) {
  const h = instanceDetail.history || []
  const last = h[h.length - 1]
  return last?.from_state || null
}
