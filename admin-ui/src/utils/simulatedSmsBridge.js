/** @typedef {{ id?: string, phone?: string, message?: string, kind?: string, created_at?: string | null }} SimSmsEntry */

const listeners = new Set()
/** @type {SimSmsEntry[]} */
const pendingBuffer = []

/** @param {SimSmsEntry} entry */
export function pushSimulatedSmsEntry(entry) {
  if (!entry?.message) return
  if (listeners.size === 0) {
    pendingBuffer.push(entry)
    if (pendingBuffer.length > 40) pendingBuffer.shift()
    return
  }
  listeners.forEach((fn) => {
    try {
      fn(entry)
    } catch (_) {
      /* ignore */
    }
  })
}

/** @param {(entry: SimSmsEntry) => void} fn */
export function subscribeSimulatedSms(fn) {
  listeners.add(fn)
  if (pendingBuffer.length) {
    const batch = pendingBuffer.splice(0, pendingBuffer.length)
    batch.forEach((entry) => {
      try {
        fn(entry)
      } catch (_) {
        /* ignore */
      }
    })
  }
  return () => listeners.delete(fn)
}

/** @param {unknown} data */
export function extractSimulatedSmsEntries(data) {
  if (!data || typeof data !== 'object') return []
  /** @type {SimSmsEntry[]} */
  const out = []
  const seen = new Set()
  const push = (entry) => {
    if (!entry || typeof entry !== 'object' || !entry.message) return
    const key = entry.id ? String(entry.id) : `${entry.phone || ''}|${entry.message}`
    if (seen.has(key)) return
    seen.add(key)
    out.push(/** @type {SimSmsEntry} */ (entry))
  }
  const d = /** @type {Record<string, unknown>} */ (data)
  if (Array.isArray(d.simulated_sms_list)) {
    d.simulated_sms_list.forEach((it) => {
      if (it && typeof it === 'object') push(/** @type {SimSmsEntry} */ (it))
    })
  }
  if (d.simulated_sms && typeof d.simulated_sms === 'object') {
    push(/** @type {SimSmsEntry} */ (d.simulated_sms))
  }
  const nested = d.response
  if (nested && typeof nested === 'object') {
    const nr = /** @type {Record<string, unknown>} */ (nested)
    if (Array.isArray(nr.simulated_sms_list)) {
      nr.simulated_sms_list.forEach((it) => {
        if (it && typeof it === 'object') push(/** @type {SimSmsEntry} */ (it))
      })
    }
    if (nr.simulated_sms && typeof nr.simulated_sms === 'object') {
      push(/** @type {SimSmsEntry} */ (nr.simulated_sms))
    }
  }
  return out
}

/** @param {unknown} data */
export function emitSimulatedSmsFromApi(data) {
  extractSimulatedSmsEntries(data).forEach(pushSimulatedSmsEntry)
}
