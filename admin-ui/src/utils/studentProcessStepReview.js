/**
 * ترتیب وضعیت‌های واقعاً طی‌شده از تاریخچهٔ نمونه (بدون تغییر وضعیت سرور).
 * @param {unknown} history
 * @param {{ states?: { code: string }[] }|null|undefined} definition
 * @param {string|null|undefined} currentState
 * @returns {string[]}
 */
export function buildStudentProcessVisitSequence(history, definition, currentState) {
  const stateSet = definition?.states?.length
    ? new Set(definition.states.map((s) => s.code).filter(Boolean))
    : null
  const list = Array.isArray(history) ? history : []
  const out = []
  for (const h of list) {
    const to = h?.to_state
    if (!to || typeof to !== 'string') continue
    if (stateSet && !stateSet.has(to)) continue
    if (out.length === 0 || out[out.length - 1] !== to) out.push(to)
  }
  if (currentState && typeof currentState === 'string') {
    const last = out[out.length - 1]
    if (last !== currentState && (!stateSet || stateSet.has(currentState))) {
      out.push(currentState)
    }
  }
  return out
}

/** وضعیت‌های قبل از جاری (آخرین عضو sequence همان current است). */
export function getPastStepsFromVisitSequence(seq) {
  if (!seq || seq.length < 2) return []
  return seq.slice(0, -1)
}

/** دکمهٔ مرور مراحل قبلی فقط با پرچم ادمین/کارمند در extra_data روشن می‌شود. */
export function isPreviousStepReviewEnabled(extraData) {
  return extraData?.allow_previous_step_review === true
}
