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

export const CTX_DOCUMENT_FIELD_REJECTION_NOTES = '__document_field_rejection_notes'
export const CTX_DOCUMENTS_RESUBMIT_FIELDS = '__documents_resubmit_fields'

/**
 * توضیح پذیرش برای هر مدرک ردشده (فیلد → متن).
 * @param {Record<string, unknown>|null|undefined} contextData
 * @returns {Record<string, string>}
 */
export function readDocumentRejectionNotes(contextData) {
  const raw = contextData?.[CTX_DOCUMENT_FIELD_REJECTION_NOTES]
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  const out = {}
  for (const [key, value] of Object.entries(raw)) {
    const note = String(value || '').trim()
    if (note) out[key] = note
  }
  return out
}

/**
 * فهرست مدارک نیازمند اصلاح به‌همراه توضیح پذیرش و یادداشت کلی.
 * @param {Record<string, unknown>|null|undefined} contextData
 * @param {Record<string, string>} [fieldLabelByName]
 * @returns {{ items: { fieldName: string, label: string, note: string }[], generalNote: string }}
 */
export function listDocumentResubmitFeedback(contextData, fieldLabelByName = {}) {
  const names = Array.isArray(contextData?.[CTX_DOCUMENTS_RESUBMIT_FIELDS])
    ? contextData[CTX_DOCUMENTS_RESUBMIT_FIELDS]
    : []
  const notes = readDocumentRejectionNotes(contextData)
  const items = names
    .map((name) => {
      const fieldName = String(name || '').trim()
      if (!fieldName) return null
      return {
        fieldName,
        label: fieldLabelByName[fieldName] || fieldName,
        note: notes[fieldName] || '',
      }
    })
    .filter(Boolean)
  const generalNote = String(contextData?.notes || '').trim()
  return { items, generalNote }
}

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
