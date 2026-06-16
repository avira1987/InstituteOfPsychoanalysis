/**
 * لینک اعلان را با nf=1 علامت می‌زند تا پس از ورود، در صورت نبود اقدام فعال، تاریخچه نمایش داده شود.
 * @param {string} actionPath مسیر نسبی مثل /panel/portal/staff?tab=pending&instance_id=...
 */
export function appendNotificationFollow(actionPath) {
  if (!actionPath || typeof actionPath !== 'string') return actionPath
  const trimmed = actionPath.trim()
  if (!trimmed.startsWith('/')) return trimmed
  const qIndex = trimmed.indexOf('?')
  const pathname = qIndex === -1 ? trimmed : trimmed.slice(0, qIndex)
  const search = qIndex === -1 ? '' : trimmed.slice(qIndex + 1)
  const params = new URLSearchParams(search)
  params.set('nf', '1')
  const out = params.toString()
  return out ? `${pathname}?${out}` : `${pathname}?nf=1`
}
