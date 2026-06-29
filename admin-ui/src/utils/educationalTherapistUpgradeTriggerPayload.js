import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeEducationalTherapistUpgradeTriggerPayload(
  instanceDetail,
  triggerEvent,
  basePayload = {},
) {
  if (instanceDetail?.process_code !== 'upgrade_to_educational_therapist') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (state === 'monitoring_review' && (triggerEvent === 'approved' || triggerEvent === 'rejected')) {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم تصمیم کمیته نظارت را تکمیل و ثبت کنید، سپس دکمهٔ تصمیم را بزنید.',
      }
    }
    const result = str(ctx.result) || str(payload.result)
    if (triggerEvent === 'approved' && result !== 'approve') {
      return { payload, error: 'در فرم «تایید» انتخاب نشده است.' }
    }
    if (triggerEvent === 'rejected' && result !== 'reject') {
      return { payload, error: 'در فرم «رد» انتخاب نشده است.' }
    }
    if (ctx.notes) payload.notes = ctx.notes
    return { payload, error: null }
  }

  if (state === 'interview_scheduling' && triggerEvent === 'interview_scheduled') {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم تنظیم وقت مصاحبه را تکمیل و ثبت کنید.',
      }
    }
    return { payload, error: null }
  }

  if (
    state === 'interview_held'
    && (triggerEvent === 'interview_approved' || triggerEvent === 'interview_rejected')
  ) {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم نتیجه مصاحبه را تکمیل و ثبت کنید.',
      }
    }
    const result = str(ctx.result) || str(payload.result)
    if (triggerEvent === 'interview_approved' && result !== 'approve') {
      return { payload, error: 'در فرم نتیجه «تایید» انتخاب نشده است.' }
    }
    if (triggerEvent === 'interview_rejected' && result !== 'reject') {
      return { payload, error: 'در فرم نتیجه «رد» انتخاب نشده است.' }
    }
    return { payload, error: null }
  }

  if (
    state === 'therapist_committee_review'
    && (triggerEvent === 'approved' || triggerEvent === 'rejected')
  ) {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم بررسی درمانگر پیشنهادی را تکمیل و ثبت کنید.',
      }
    }
    const result = str(ctx.result) || str(payload.result)
    if (triggerEvent === 'approved' && result !== 'approve') {
      return { payload, error: 'در فرم «تایید درمانگر» انتخاب نشده است.' }
    }
    if (triggerEvent === 'rejected' && result !== 'reject') {
      return { payload, error: 'در فرم «رد درمانگر» انتخاب نشده است.' }
    }
    return { payload, error: null }
  }

  return { payload, error: null }
}
