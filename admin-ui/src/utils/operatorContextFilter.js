/**
 * کلیدهای context_data که برای اپراتور غیرفنی نباید نمایش داده شوند
 * (لاگ یکپارچه‌سازی، شناسه‌های داخلی، …).
 */
export const OPERATOR_HIDDEN_CONTEXT_KEYS = [
  'integration_events',
  /** ارجاع داخلی به نمونهٔ start_therapy؛ برای کارمند کاربردی نیست */
  'parent_start_therapy_instance_id',
]

/**
 * کپی کم‌عمق از context بدون کلیدهای فنی.
 * @param {object|null|undefined} contextData
 * @returns {object}
 */
export function filterContextForOperators(contextData) {
  if (!contextData || typeof contextData !== 'object' || Array.isArray(contextData)) {
    return {}
  }
  const out = { ...contextData }
  for (const k of OPERATOR_HIDDEN_CONTEXT_KEYS) {
    delete out[k]
  }
  return out
}
