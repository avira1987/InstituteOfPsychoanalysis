import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'
import { canChooseRegister, parseWeeks } from './studentNonRegistrationDisplay'

const MEETING_KEYS = [
  'committee_meeting_at',
  'committee_meeting_mode',
  'committee_meeting_link',
  'committee_meeting_location_fa',
]

const DECISION_TO_TRIGGER = {
  register: 'choice_register',
  leave: 'choice_leave',
  withdrawal: 'choice_withdrawal',
}

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

function ensureMeetingPayload(instanceDetail, payload) {
  const ctx = instanceDetail?.context_data || {}
  const out = { ...(payload || {}) }
  for (const key of MEETING_KEYS) {
    if (out[key] == null || out[key] === '') {
      if (ctx[key] != null && ctx[key] !== '') out[key] = ctx[key]
    }
  }
  return out
}

function validateMeetingFields(payload) {
  const at = str(payload.committee_meeting_at)
  if (!at) {
    return 'تاریخ و ساعت جلسه در فرم ثبت نشده است.'
  }
  const mode = str(payload.committee_meeting_mode)
  if (mode === 'online' && !str(payload.committee_meeting_link)) {
    return 'برای جلسه آنلاین، لینک جلسه در فرم الزامی است.'
  }
  if (mode === 'in_person' && !str(payload.committee_meeting_location_fa)) {
    return 'برای جلسه حضوری، آدرس یا محل در فرم الزامی است.'
  }
  if (mode && mode !== 'online' && mode !== 'in_person') {
    return 'نحوهٔ برگزاری جلسه را مشخص کنید (حضوری یا آنلاین).'
  }
  return null
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeNonRegistrationTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  if (instanceDetail?.process_code !== 'student_non_registration') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (triggerEvent === 'meeting_scheduled') {
    if (!submitted.list_generated) {
      return {
        payload,
        error: 'ابتدا فرم «تعیین جلسه» را تکمیل و ثبت کنید، سپس دکمهٔ ثبت جلسه را بزنید.',
      }
    }
    payload = ensureMeetingPayload(instanceDetail, payload)
    const err = validateMeetingFields(payload)
    if (err) return { payload, error: err }
    return { payload, error: null }
  }

  if (triggerEvent === 'choice_register' || triggerEvent === 'choice_leave' || triggerEvent === 'choice_withdrawal') {
    if (!submitted.meeting_held) {
      return {
        payload,
        error: 'ابتدا فرم «ثبت نتیجه جلسه» را تکمیل و ثبت کنید، سپس دکمهٔ تصمیم را بزنید.',
      }
    }
    const decision = str(payload.decision) || str(ctx.decision)
    const expected = DECISION_TO_TRIGGER[decision]
    if (!expected) {
      return { payload, error: 'تصمیم جلسه در فرم ثبت نشده است.' }
    }
    if (expected !== triggerEvent) {
      return {
        payload,
        error: 'تصمیم ثبت‌شده در فرم با دکمهٔ انتخاب‌شده هم‌خوان نیست؛ دکمهٔ متناسب با تصمیم را بزنید.',
      }
    }
    if (triggerEvent === 'choice_register') {
      const weeks = parseWeeks(ctx.weeks_since_start ?? ctx.weeks_since_term_start)
      if (!canChooseRegister(weeks)) {
        return {
          payload,
          error: 'گزینهٔ ثبت‌نام فقط تا ۴ هفته پس از شروع کلاس‌ها مجاز است.',
        }
      }
    }
    payload.decision = decision
    return { payload, error: null }
  }

  return { payload, error: null }
}
