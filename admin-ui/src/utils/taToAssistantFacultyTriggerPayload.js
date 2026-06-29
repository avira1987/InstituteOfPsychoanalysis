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
export function mergeTaToAssistantFacultyTriggerPayload(
  instanceDetail,
  triggerEvent,
  basePayload = {},
) {
  if (instanceDetail?.process_code !== 'ta_to_assistant_faculty') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (state === 'supervision_review' && (triggerEvent === 'approved' || triggerEvent === 'rejected')) {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم «بررسی ارتقا به دستیار هیئت علمی» را تکمیل و ثبت کنید، سپس دکمهٔ تصمیم را بزنید.',
      }
    }
    const result = str(ctx.result) || str(payload.result)
    if (triggerEvent === 'approved' && result !== 'approve') {
      return { payload, error: 'در فرم «تایید صلاحیت» انتخاب نشده است.' }
    }
    if (triggerEvent === 'rejected' && result !== 'reject') {
      return { payload, error: 'در فرم «رد صلاحیت» انتخاب نشده است.' }
    }
    if (ctx.notes) payload.notes = ctx.notes
    return { payload, error: null }
  }

  return { payload, error: null }
}
