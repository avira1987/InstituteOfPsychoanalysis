/**
 * شمارهٔ مرحلهٔ SOP از پاسخ API (فیلد sop_order یا داخل config).
 */
export function resolveProcessSopOrder(process) {
  if (!process || typeof process !== 'object') return null
  const raw = process.sop_order ?? process.config?.sop_order
  if (raw == null || raw === '') return null
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw
  const n = parseInt(String(raw), 10)
  return Number.isFinite(n) ? n : null
}
