import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'

const MEETING_KEYS = [
  'committee_meeting_at',
  'committee_meeting_mode',
  'committee_meeting_link',
  'committee_meeting_location_fa',
]

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeFullEducationLeaveTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  if (instanceDetail?.process_code !== 'full_education_leave') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (triggerEvent === 'committee_set_meeting') {
    if (!submitted[state]) {
      return { payload, error: 'ابتدا فرم «تعیین جلسه» را تکمیل و ثبت کنید، سپس دکمهٔ ثبت جلسه را بزنید.' }
    }
    for (const key of MEETING_KEYS) {
      if (payload[key] == null || payload[key] === '') {
        if (ctx[key] != null && ctx[key] !== '') payload[key] = ctx[key]
      }
    }
    const at = str(payload.committee_meeting_at)
    if (!at) {
      return { payload, error: 'تاریخ و ساعت جلسه در فرم ثبت نشده است.' }
    }
    const mode = str(payload.committee_meeting_mode)
    if (mode === 'online' && !str(payload.committee_meeting_link)) {
      return { payload, error: 'برای جلسه آنلاین، لینک جلسه در فرم الزامی است.' }
    }
    if (mode === 'in_person' && !str(payload.committee_meeting_location_fa)) {
      return { payload, error: 'برای جلسه حضوری، آدرس یا محل در فرم الزامی است.' }
    }
    return { payload, error: null }
  }

  if (triggerEvent === 'committee_rejected') {
    if (!submitted.committee_decision) {
      return { payload, error: 'ابتدا فرم «ثبت نتیجهٔ نهایی» را تکمیل و ثبت کنید.' }
    }
    const reason = str(payload.rejection_reason_fa) || str(ctx.rejection_reason_fa)
    if (!reason) {
      return { payload, error: 'شرح توافقات / علت رد را در فرم وارد و ثبت کنید.' }
    }
    payload.rejection_reason_fa = reason
    return { payload, error: null }
  }

  if (triggerEvent === 'therapist_assigned') {
    if (!submitted.therapist_assignment) {
      return { payload, error: 'ابتدا فرم «تعیین تکلیف درمانگر» را تکمیل و ثبت کنید.' }
    }
    const decision = str(payload.therapist_decision) || str(ctx.therapist_decision)
    if (!decision || !['continue_general', 'release_slot'].includes(decision)) {
      return { payload, error: 'یکی از دو حالت تعیین تکلیف درمانگر را در فرم انتخاب و ثبت کنید.' }
    }
    payload.therapist_decision = decision
    return { payload, error: null }
  }

  return { payload, error: null }
}
