import { PROCESS_LABELS_FA, STATE_LABELS_FA } from './processMetadataLabels'
import { toFaDigits } from './persianDigits'

/** نقش کاربر در رابط کاربری فارسی */
export const ROLE_LABELS_FA = {
  staff: 'کارمند اداری',
  student: 'دانشجو',
  therapist: 'درمانگر آموزشی',
  supervisor: 'سوپروایزر',
  admin: 'مدیر سیستم',
  committee: 'عضو کمیته',
  site_manager: 'مدیر سایت',
  financial: 'مالی',
  instructor: 'مدرس',
  ta: 'کمک‌مدرس',
}

/** برچسب فارسی نقش؛ در نبود نقشه، متن اصلی نمایش داده می‌شود. */
export function formatActorRole(role) {
  if (role == null || role === '') return '—'
  return ROLE_LABELS_FA[role] || role
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
