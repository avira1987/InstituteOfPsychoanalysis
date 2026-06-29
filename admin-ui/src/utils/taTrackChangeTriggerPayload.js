import { CTX_STUDENT_FORMS_SUBMITTED } from './processFormsStudent'
import { normalizeTrackList } from './taTrackChangeDisplay'

function str(v) {
  return typeof v === 'string' ? v.trim() : v != null ? String(v).trim() : ''
}

/**
 * @param {object} instanceDetail
 * @param {string} triggerEvent
 * @param {object} basePayload
 * @returns {{ payload: object, error: string | null }}
 */
export function mergeTaTrackChangeTriggerPayload(
  instanceDetail,
  triggerEvent,
  basePayload = {},
) {
  if (instanceDetail?.process_code !== 'ta_track_change') {
    return { payload: basePayload, error: null }
  }

  const ctx = instanceDetail?.context_data || {}
  const submitted = ctx[CTX_STUDENT_FORMS_SUBMITTED] || {}
  const state = instanceDetail?.current_state
  let payload = { ...(basePayload || {}) }

  if (state === 'ta_click' && triggerEvent === 'path_chosen') {
    if (!submitted[state] && !submitted.ta_click) {
      return {
        payload,
        error: 'ابتدا فرم «انتخاب مسیر» را تکمیل و ثبت کنید، سپس دکمهٔ ارسال درخواست را بزنید.',
      }
    }
    const path = str(ctx.path) || str(payload.path)
    if (!path || !['add', 'change'].includes(path)) {
      return { payload, error: 'مسیر درخواست (اضافه یا تغییر رسته) را در فرم انتخاب کنید.' }
    }
    payload.path = path
    return { payload, error: null }
  }

  if (state === 'course_committee_review' && triggerEvent === 'meeting_registered') {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم «ثبت زمان و مشخصات جلسه» را تکمیل و ثبت کنید.',
      }
    }
    for (const key of ['meeting_date', 'meeting_time', 'meeting_type']) {
      if (payload[key] == null || payload[key] === '') {
        if (ctx[key] != null && ctx[key] !== '') payload[key] = ctx[key]
      }
    }
    const meetingType = str(payload.meeting_type) || str(ctx.meeting_type)
    if (!str(payload.meeting_date) && !str(ctx.meeting_date)) {
      return { payload, error: 'تاریخ جلسه در فرم ثبت نشده است.' }
    }
    if (!str(payload.meeting_time) && !str(ctx.meeting_time)) {
      return { payload, error: 'ساعت جلسه در فرم ثبت نشده است.' }
    }
    if (!meetingType) {
      return { payload, error: 'نحوهٔ برگزاری جلسه را در فرم مشخص کنید.' }
    }
    if (meetingType === 'online') {
      const link = str(payload.meeting_link) || str(ctx.meeting_link)
      if (!link) {
        return {
          payload,
          error: 'برای جلسه آنلاین، لینک جلسه هنوز آماده نیست — فرم را دوباره ثبت کنید یا با پشتیبانی تماس بگیرید.',
        }
      }
      payload.meeting_link = link
    }
    if (meetingType === 'in_person') {
      payload.meeting_location_fa = str(payload.meeting_location_fa)
        || str(ctx.meeting_location_fa)
        || 'مکان انستیتو'
    }
    return { payload, error: null }
  }

  if (state === 'meeting_scheduled' && (triggerEvent === 'approved' || triggerEvent === 'rejected')) {
    if (!submitted[state]) {
      return {
        payload,
        error: 'ابتدا فرم «نتیجه جلسه و تخصیص رسته‌ها» را تکمیل و ثبت کنید.',
      }
    }
    const result = str(ctx.result) || str(payload.result)
    if (triggerEvent === 'approved' && result !== 'approve') {
      return { payload, error: 'در فرم «موافقت» انتخاب نشده است.' }
    }
    if (triggerEvent === 'rejected' && result !== 'reject') {
      return { payload, error: 'در فرم «عدم موافقت» انتخاب نشده است.' }
    }
    if (triggerEvent === 'approved') {
      const tracks = normalizeTrackList(ctx.new_tracks || payload.new_tracks)
      if (!tracks.length) {
        return { payload, error: 'حداقل یک رسته جدید باید انتخاب شود.' }
      }
      payload.new_tracks = tracks
      payload.path = str(ctx.path) || str(payload.path)
    }
    return { payload, error: null }
  }

  return { payload, error: null }
}
