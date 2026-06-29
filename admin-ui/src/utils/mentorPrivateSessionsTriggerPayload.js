import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'
import { isMentorPrivateSessionsProcess } from './mentorPrivateSessionsDisplay'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

function sessionFieldsFromCtx(ctx = {}, submitted = {}) {
  const formData = submitted.instructor_click || submitted.mentor_sessions_form || {}
  return {
    session1Date: ctx.session_1_date || formData.session_1_date,
    session1Time: str(ctx.session_1_time || formData.session_1_time),
    session2Date: ctx.session_2_date || formData.session_2_date,
    session2Time: str(ctx.session_2_time || formData.session_2_time),
  }
}

function sessionFieldsPresent(fields) {
  return Boolean(
    fields.session1Date
    && fields.session1Time
    && fields.session2Date
    && fields.session2Time,
  )
}

function parseDateTime(dateVal, timeVal) {
  if (!dateVal) return null
  const dateStr = String(dateVal).slice(0, 10)
  const timeStr = str(timeVal) || '00:00'
  const dt = new Date(`${dateStr}T${timeStr}`)
  return Number.isNaN(dt.getTime()) ? null : dt
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeMentorPrivateSessionsTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  const processCode = instanceDetail?.process_code
  if (!isMentorPrivateSessionsProcess(processCode)) {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state || ''
  const payload = { ...(basePayload || {}) }

  if (triggerEvent === 'sessions_entered' && state === 'instructor_click') {
    const fields = sessionFieldsFromCtx(ctx, submitted)
    if (!sessionFieldsPresent(fields)) {
      return {
        payload,
        error: 'ابتدا فرم را تکمیل کنید: تاریخ و ساعت هر دو جلسهٔ تدریس خصوصی الزامی است.',
      }
    }
    const dt1 = parseDateTime(fields.session1Date, fields.session1Time)
    const dt2 = parseDateTime(fields.session2Date, fields.session2Time)
    if (dt1 && dt2 && dt2.getTime() < dt1.getTime()) {
      return {
        payload,
        error: 'زمان جلسهٔ دوم نمی‌تواند قبل از جلسهٔ اول باشد.',
      }
    }
  }

  return { payload, error: null }
}
