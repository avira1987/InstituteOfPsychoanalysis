import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'
import { isLiveSessionPrepProcess } from './liveSessionPrepDisplay'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

function scheduleFieldsPresent(ctx = {}) {
  return Boolean(
    str(ctx.instructor_id)
    && str(ctx.therapist_id)
    && ctx.session_date
    && str(ctx.session_time),
  )
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeLiveSessionPrepTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  const processCode = instanceDetail?.process_code
  if (!isLiveSessionPrepProcess(processCode)) {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state || ''
  let payload = { ...(basePayload || {}) }

  if (triggerEvent === 'referral_submitted' && state === 'patient_referral') {
    const hasPatient = str(ctx.patient_first_name) && str(ctx.patient_last_name) && str(ctx.patient_phone)
    if (!hasPatient && !submitted.patient_referral) {
      return {
        payload,
        error: 'ابتدا فرم ارجاع بیمار را تکمیل و ثبت کنید (نام، نام خانوادگی و شماره تماس).',
      }
    }
    return { payload, error: null }
  }

  if (state === 'coordination_pending') {
    if (triggerEvent === 'time_registered') {
      if (!submitted.coordination_pending && !scheduleFieldsPresent(ctx)) {
        return {
          payload,
          error: 'ابتدا فرم تعیین زمان (مدرس، درمانگر، تاریخ و ساعت) را تکمیل و ثبت کنید.',
        }
      }
      if (!scheduleFieldsPresent(ctx)) {
        return {
          payload,
          error: 'مدرس، درمانگر، تاریخ و ساعت جلسه الزامی است.',
        }
      }
      return {
        payload: {
          ...payload,
          session_time_registered: true,
          to_state: 'session_scheduled',
        },
        error: null,
      }
    }

    if (triggerEvent === 'no_time_agreed') {
      return {
        payload: {
          ...payload,
          session_time_registered: false,
          to_state: 'coordination_closed',
        },
        error: null,
      }
    }
  }

  return { payload, error: null }
}
