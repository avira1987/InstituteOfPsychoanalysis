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

/**
 * آیا این وضعیت یکی از مراحل بررسی/تکمیل مدارک است؟
 * @param {string} state کد وضعیت فعلی فرایند
 * @returns {boolean}
 */
export function isDocumentReviewState(state) {
  if (!state) return false
  return DOCUMENT_REVIEW_STATE_CODES.includes(String(state).trim())
}
