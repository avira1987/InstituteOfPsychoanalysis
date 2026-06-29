import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'
import { normalizeReferralRows } from './internBulkPatientReferralDisplay'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

function rowsFrom(instanceDetail, payload) {
  const ctx = instanceDetail?.context_data || {}
  const raw = payload?.patient_referral_rows ?? ctx.patient_referral_rows
  return normalizeReferralRows(raw)
}

function validateStudentContacts(rows) {
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i]
    if (!row.contacted) {
      return `برای «${row.patient_name}» تیک صحبت الزامی است.`
    }
    if (!str(row.contact_notes)) {
      return `توضیحات صحبت با «${row.patient_name}» الزامی است.`
    }
  }
  return null
}

function validateCommitteeRows(rows) {
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i]
    if (!row.committee_contacted) {
      return `تیک صحبت کمیته برای «${row.patient_name}» الزامی است.`
    }
    if (!str(row.referral_notes)) {
      return `توضیحات ارجاع برای «${row.patient_name}» الزامی است.`
    }
  }
  return null
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeReferralTriggerPayload(instanceDetail, triggerEvent, basePayload = {}) {
  if (instanceDetail?.process_code !== 'intern_bulk_patient_referral') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  let payload = { ...(basePayload || {}) }

  for (const key of ['meeting_datetime', 'meeting_held', 'referral_conditions', 'patient_referral_rows']) {
    if (payload[key] == null || payload[key] === '' || (Array.isArray(payload[key]) && !payload[key].length)) {
      if (ctx[key] != null && ctx[key] !== '') payload[key] = ctx[key]
    }
  }

  const rows = rowsFrom(instanceDetail, payload)

  if (triggerEvent === 'meeting_and_conditions_logged') {
    if (!submitted.supervision_start) {
      return {
        payload,
        error: 'ابتدا فرم «ثبت جلسه و شرایط ارجاع» را تکمیل و ثبت کنید.',
      }
    }
    if (!str(payload.referral_conditions)) {
      return { payload, error: 'شرایط ارجاع الزامی است.' }
    }
    if (!rows.length) {
      return { payload, error: 'حداقل یک بیمار در جدول ثبت کنید.' }
    }
    payload.patient_referral_rows = rows
    return { payload, error: null }
  }

  if (triggerEvent === 'student_patient_contacts_done') {
    const err = validateStudentContacts(rows)
    if (err) return { payload, error: err }
    payload.patient_referral_rows = rows
    return { payload, error: null }
  }

  if (triggerEvent === 'committee_referral_notes_complete') {
    if (!submitted.general_therapy_committee_review) {
      return {
        payload,
        error: 'ابتدا فرم کمیته درمان عموم را تکمیل و ثبت کنید.',
      }
    }
    const err = validateCommitteeRows(rows)
    if (err) return { payload, error: err }
    payload.patient_referral_rows = rows
    return { payload, error: null }
  }

  if (triggerEvent === 'coordination_followup_complete') {
    if (!submitted.coordination_followup) {
      return {
        payload,
        error: 'ابتدا فرم پیگیری را تکمیل و ثبت کنید.',
      }
    }
    for (const row of rows) {
      if (!row.followup_done) {
        return {
          payload,
          error: `تیک پیگیری برای «${row.patient_name}» الزامی است.`,
        }
      }
    }
    payload.patient_referral_rows = rows
    return { payload, error: null }
  }

  return { payload, error: null }
}
