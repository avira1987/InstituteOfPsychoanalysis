import { PROCESS_LABELS_FA, PROCESS_STATE_LABELS_FA, STATE_LABELS_FA } from './processMetadataLabels'
import { toFaDigits } from './persianDigits'
import { labelRoleFa } from './roleLabels'

/** @deprecated از roleLabels.js استفاده کنید — برای سازگاری عقب‌رو export می‌شود */
export { ROLE_LABELS_FA_MAP as ROLE_LABELS_FA } from './roleLabels'

/** برچسب فارسی نقش؛ در نبود نقشه، «نقش نامشخص (کد)». */
export function formatActorRole(role) {
  return labelRoleFa(role)
}

/** رویداد/تریگر: همان واژه‌نامهٔ وضعیت‌ها (بسیاری از تریگرها در همان فهرست‌اند). */
export function labelTriggerEvent(event) {
  if (event == null || event === '') return '—'
  return STATE_LABELS_FA[event] || event
}

/** عنوان فارسی فرایند از متادیتا؛ در نبود، همان کد (برای دیباگ). */
export function labelProcess(code) {
  if (code == null || code === '') return '—'
  return PROCESS_LABELS_FA[code] || code
}

/** عنوان فارسی وضعیت/مرحله از متادیتا. */
export function labelState(state) {
  if (state == null || state === '') return '—'
  return STATE_LABELS_FA[state] || state
}

/** برچسب نمایشی وضعیت: اول واژه‌نامهٔ مخصوص فرایند، بعد واژهٔ عمومی، بعد متادیتا. */
export function resolveStateDisplayLabel(stateCode, metadataNameFa, processCode) {
  if (processCode && PROCESS_STATE_LABELS_FA[processCode]?.[stateCode]) {
    return PROCESS_STATE_LABELS_FA[processCode][stateCode]
  }
  if (stateCode && STATE_LABELS_FA[stateCode]) {
    return STATE_LABELS_FA[stateCode]
  }
  if (metadataNameFa) return metadataNameFa
  return labelState(stateCode)
}

/**
 * کدهای دمو مثل AUTO-DEMO-committees_review برای کاربر نهایی گیج‌کننده‌اند؛
 * به‌جای آن برچسب فارسی فرایند مرتبط نمایش داده می‌شود.
 */
export function formatStudentCodeDisplay(code) {
  if (code == null || code === '') return '—'
  const s = String(code)
  const m = s.match(/^AUTO-DEMO-(.+)$/)
  if (m) {
    const suffix = m[1]
    const procLabel = PROCESS_LABELS_FA[suffix]
    if (procLabel) return toFaDigits(`دانشجوی دمو — ${procLabel}`)
    return toFaDigits(`دانشجوی دمو (${suffix})`)
  }
  return toFaDigits(s)
}
