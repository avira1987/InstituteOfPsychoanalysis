import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

function tracksList(ctx) {
  const raw = ctx.tracks
  if (Array.isArray(raw)) return raw.filter((x) => x != null && String(x).trim() !== '')
  if (raw != null && String(raw).trim() !== '') return [String(raw)]
  return []
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeUpgradeToTaTriggerPayload(
  instanceDetail,
  triggerEvent,
  basePayload = {},
) {
  if (instanceDetail?.process_code !== 'upgrade_to_ta') {
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

  if (state === 'interview_held' && (triggerEvent === 'approved' || triggerEvent === 'rejected')) {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم نتیجه مصاحبه را تکمیل و ثبت کنید.',
      }
    }
    const result = str(ctx.result) || str(payload.result)
    if (triggerEvent === 'approved' && result !== 'approve') {
      return { payload, error: 'در فرم نتیجه «تایید» انتخاب نشده است.' }
    }
    if (triggerEvent === 'rejected' && result !== 'reject') {
      return { payload, error: 'در فرم نتیجه «رد» انتخاب نشده است.' }
    }
    return { payload, error: null }
  }

  if (state === 'track_selection' && triggerEvent === 'tracks_registered') {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم ثبت رسته‌ها را تکمیل و ثبت کنید.',
      }
    }
    const tracks = tracksList(ctx)
    if (!tracks.length) {
      return { payload, error: 'حداقل یک رسته باید انتخاب شود.' }
    }
    payload.tracks = tracks
    return { payload, error: null }
  }

  if (state === 'commitment_signature' && triggerEvent === 'commitment_signed') {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا تعهدنامه را با کد پیامکی امضا و ثبت کنید.',
      }
    }
    if (!ctx.acknowledge && !payload.acknowledge) {
      return { payload, error: 'پذیرش تعهدنامه الزامی است.' }
    }
    if (!ctx.step_otp_verified && !ctx.otp_code) {
      return { payload, error: 'کد پیامکی تأیید نشده است.' }
    }
    return { payload, error: null }
  }

  if (state === 'student_click' && triggerEvent === 'conditions_met') {
    if (ctx.ta_eligibility_met !== true) {
      return {
        payload,
        error: 'شرایط ارتقا احراز نشده است؛ ابتدا چهار شرط را در پنل بالا بررسی کنید.',
      }
    }
    return { payload, error: null }
  }

  return { payload, error: null }
}
