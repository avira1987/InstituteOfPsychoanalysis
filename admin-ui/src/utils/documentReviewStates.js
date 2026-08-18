/**
 * مراحل «بررسی/تکمیل مدارک» مخصوص پذیرش/کارمند (و مسئول سایت) است.
 * این مراحل نباید در پنل‌های کمیته، درمانگر و سوپروایزر نمایش داده شوند؛
 * تأیید مدارک اپلودشدهٔ دانشجو فقط در پنل کارمند انجام می‌شود.
 *
 * هم‌راستا با بک‌اند: app/services/portal_role_inbox.py (_DOCUMENT_REVIEW_STATE_CODES).
 */
export const DOCUMENT_REVIEW_STATE_CODES = Object.freeze([
  'documents_review',
  'documents_incomplete',
  'documents_upload',
])

export const DOCUMENT_REVIEW_DECISION_TRIGGERS = Object.freeze([
  'documents_approved',
  'documents_rejected',
])

/**
 * آیا این وضعیت یکی از مراحل بررسی/تکمیل مدارک است؟
 * @param {string} state کد وضعیت فعلی فرایند
 * @returns {boolean}
 */
export function isDocumentReviewState(state) {
  if (!state) return false
  return DOCUMENT_REVIEW_STATE_CODES.includes(String(state).trim())
}

/**
 * آیا این تریگر تصمیم نهایی اپراتور روی مدارک است؟
 * @param {string} triggerEvent
 * @returns {boolean}
 */
export function isDocumentReviewDecisionTrigger(triggerEvent) {
  return DOCUMENT_REVIEW_DECISION_TRIGGERS.includes(String(triggerEvent || '').trim())
}

/**
 * پیام صریح برای اپراتور پس از تأیید یا رد مدارک.
 * باید بگوید کار بررسی مدارک همین دانشجو تمام شده (نه فقط «ثبت شد»).
 *
 * @param {{ triggerEvent?: string, studentCodeDisplay?: string, toStateLabel?: string }} opts
 * @returns {string}
 */
export function documentReviewDecisionMessageFa({
  triggerEvent,
  studentCodeDisplay = '',
  toStateLabel = '',
} = {}) {
  const who =
    studentCodeDisplay && studentCodeDisplay !== '—'
      ? `دانشجو ${studentCodeDisplay}`
      : 'این دانشجو'
  const event = String(triggerEvent || '').trim()
  if (event === 'documents_approved') {
    const next = toStateLabel ? ` وضعیت بعدی: ${toStateLabel}.` : ''
    return `کار تأیید مدارک ${who} تمام شد. این پرونده از صف بررسی خارج شد.${next}`
  }
  if (event === 'documents_rejected') {
    return `نواقص مدارک ${who} ثبت شد و پرونده برای تکمیل دوباره به دانشجو برگشت.`
  }
  return toStateLabel ? `ثبت شد — وضعیت جدید: ${toStateLabel}` : 'ثبت شد'
}

/**
 * اگر تریگر مربوط به تصمیم مدارک باشد متن آمادهٔ toast برمی‌گردد؛ وگرنه null.
 *
 * @param {string} triggerEvent
 * @param {{ studentCodeDisplay?: string, toStateLabel?: string }} [opts]
 * @returns {string | null}
 */
export function operatorDocumentReviewToastFa(
  triggerEvent,
  { studentCodeDisplay, toStateLabel } = {},
) {
  if (!isDocumentReviewDecisionTrigger(triggerEvent)) return null
  return documentReviewDecisionMessageFa({
    triggerEvent,
    studentCodeDisplay,
    toStateLabel,
  })
}
