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
export function mergeCommissionReviewTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  if (instanceDetail?.process_code !== 'specialized_commission_review') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (triggerEvent === 'commission_approved' || triggerEvent === 'commission_rejected') {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم «بررسی و رأی کمیسیون تخصصی» را تکمیل و ثبت کنید، سپس دکمهٔ تصمیم را بزنید.',
      }
    }
    const meeting = str(payload.commission_meeting_notes_fa) || str(ctx.commission_meeting_notes_fa)
    const opinion = str(payload.commission_opinion_fa) || str(ctx.commission_opinion_fa)
    if (!meeting) {
      return { payload, error: 'یادداشت جلسه با دانشجو در فرم ثبت نشده است.' }
    }
    if (!opinion) {
      return { payload, error: 'نظر تخصصی کمیسیون در فرم ثبت نشده است.' }
    }
    payload.commission_meeting_notes_fa = meeting
    payload.commission_opinion_fa = opinion
    if (triggerEvent === 'commission_approved') {
      payload.commission_result = 'eligibility_confirmed'
    } else {
      payload.commission_result = 'ineligibility'
    }
    return { payload, error: null }
  }

  return { payload, error: null }
}
