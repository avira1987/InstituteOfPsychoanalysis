import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

function validateTherapyHours(courseType, weeklySessions) {
  const ws = Number(weeklySessions)
  if (!Number.isFinite(ws)) return 'تعداد جلسات هفتگی را در فرم ثبت کنید.'
  if (courseType === 'comprehensive' && ws !== 2) {
    return 'در دوره جامع باید دقیقاً ۲ جلسه در هفته انتخاب شود.'
  }
  if (courseType === 'introductory' && (ws < 1 || ws > 2)) {
    return 'در دوره آشنایی باید ۱ یا ۲ جلسه در هفته انتخاب شود.'
  }
  return null
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeReturnToFullEducationTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  if (instanceDetail?.process_code !== 'return_to_full_education') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (triggerEvent === 'proceed' && state === 'return_request') {
    return { payload, error: null }
  }

  if (triggerEvent === 'therapist_selected' && state === 'therapist_selection') {
    if (!submitted.therapist_selection) {
      return {
        payload,
        error: 'ابتدا فرم انتخاب درمانگر را تکمیل و ثبت کنید، سپس دکمهٔ ادامه را بزنید.',
      }
    }
    const courseType = ctx.course_type || 'introductory'
    const ws = payload.weekly_sessions ?? ctx.weekly_sessions
    const hoursErr = validateTherapyHours(courseType, ws)
    if (hoursErr) return { payload, error: hoursErr }
    if (!str(payload.therapist_id ?? ctx.therapist_id)) {
      return { payload, error: 'درمانگر آموزشی انتخاب نشده است.' }
    }
    if (!str(payload.first_session_date ?? ctx.first_session_date)) {
      return { payload, error: 'تاریخ اولین جلسه در فرم ثبت نشده است.' }
    }
    return { payload, error: null }
  }

  if (triggerEvent === 'supervisor_selected' && state === 'supervisor_selection') {
    if (!submitted.supervisor_selection) {
      return {
        payload,
        error: 'ابتدا فرم انتخاب سوپروایزر را تکمیل و ثبت کنید، سپس دکمهٔ ادامه را بزنید.',
      }
    }
    if (!str(payload.supervisor_id ?? ctx.supervisor_id)) {
      return { payload, error: 'سوپروایزر انتخاب نشده است.' }
    }
    if (!str(payload.first_supervision_date ?? ctx.first_supervision_date)) {
      return { payload, error: 'تاریخ اولین جلسه سوپرویژن در فرم ثبت نشده است.' }
    }
    return { payload, error: null }
  }

  return { payload, error: null }
}
