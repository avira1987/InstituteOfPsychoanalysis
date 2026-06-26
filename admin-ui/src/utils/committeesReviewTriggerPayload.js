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
export function mergeCommitteesReviewTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  if (instanceDetail?.process_code !== 'committees_review') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (triggerEvent === 'supervision_recommendation_submitted') {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم «پیشنهاد کمیته نظارت» را تکمیل و ثبت کنید، سپس دکمهٔ ثبت پیشنهاد را بزنید.',
      }
    }
    const code = str(payload.nezarat_recommendation_code) || str(ctx.nezarat_recommendation_code)
    const text = str(payload.nezarat_recommendation_fa) || str(ctx.nezarat_recommendation_fa)
    if (!code) {
      return { payload, error: 'نوع پیشنهاد (ادامه یا قطع) را در فرم انتخاب کنید.' }
    }
    if (!text) {
      return { payload, error: 'توضیحات پیشنهاد کمیته نظارت را در فرم وارد کنید.' }
    }
    payload.nezarat_recommendation_code = code
    payload.nezarat_recommendation_fa = text
    payload.recommendation_fa = text
    return { payload, error: null }
  }

  if (triggerEvent === 'education_verdict_continue' || triggerEvent === 'education_verdict_terminate') {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم «حکم نهایی کمیته آموزش» را تکمیل و ثبت کنید، سپس دکمهٔ حکم را بزنید.',
      }
    }
    const notes = str(payload.education_verdict_notes_fa) || str(ctx.education_verdict_notes_fa)
    if (notes) payload.education_verdict_notes_fa = notes
    return { payload, error: null }
  }

  return { payload, error: null }
}
