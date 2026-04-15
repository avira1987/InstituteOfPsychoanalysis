/**
 * متن دکمه‌های انتقال مرحله در پنل دانشجو.
 * description_fa ترنزیشن برای مستند داخلی/کارمند است؛ روی دکمه نمایش داده نمی‌شود.
 */
import { labelState } from './processDisplay'

/** توضیح ثابت بالای بلوک دکمه‌ها */
export const STUDENT_TRANSITION_CTA_INTRO =
  'پس از انجام کارهای همین صفحه، با زدن دکمهٔ زیر مرحلهٔ بعد در فرایند ثبت می‌شود. اگر در این مرحله پرداخت به درگاه بانک یا ارسال پیامک برای شما پیش‌بینی شده، همان‌ها به‌صورت خودکار توسط سامانه انجام می‌شود؛ این دکمه فقط ثبتِ تکمیل کار شما و رفتن به مرحلهٔ بعد است.'

/**
 * @param {object} transition
 * @param {number} transitionCount
 */
export function getStudentTransitionButtonMain(transition, transitionCount) {
  const te = transition?.trigger_event
  const ts = transition?.to_state
  if (te === 'leave_activated' && ts === 'on_leave') {
    return 'تأیید نهایی: فعال‌سازی مرخصی و مسدود کردن ثبت‌نام'
  }
  if (te === 'student_registered' && ts === 'returned') {
    return 'ثبت بازگشت: تأیید دستی ثبت‌نام ترم آینده'
  }
  if (te === 'student_initiated_payment' && ts === 'payment_selection') {
    return 'ادامه به انتخاب جلسات و تسویه'
  }
  if (te === 'payment_selection_submitted' && ts === 'awaiting_payment') {
    return 'رفتن به درگاه پرداخت'
  }
  if (te === 'student_confirmed_with_violation' && ts === 'reduction_with_violation') {
    return 'تأیید نهایی با علم به تخلف و اعمال کاهش'
  }
  const next = labelState(transition?.to_state)
  if (transitionCount > 1) {
    return `ادامه به «${next}»`
  }
  return 'ادامه و ثبت مرحله'
}

/** زیرنویس کوتاه زیر متن اصلی دکمه */
export function getStudentTransitionButtonSub(transition) {
  const te = transition?.trigger_event
  const ts = transition?.to_state
  if (te === 'student_registered' && ts === 'returned') {
    return 'پس از ثبت واقعی دروس ترم در سامانه، این دکمه را بزنید تا مسیر بازگشت بسته شود (اتصال خودکار به سیستم ثبت‌نام ترم وجود ندارد)'
  }
  const next = labelState(transition?.to_state)
  if (!next || next === '—') return ''
  return `→ ${next}`
}

/** برای title / دسترسی‌پذیری: توضیح فنی از متادیتا */
export function getStudentTransitionTooltip(transition) {
  const raw = (transition?.description_fa || transition?.description || transition?.trigger_event || '').trim()
  const ts = transition?.to_state
  const next = labelState(ts)
  if (raw && ts) return `${raw}\n(مرحلهٔ بعد در سیستم: ${next})`
  if (raw) return raw
  if (ts) return `مرحلهٔ بعد: ${next}`
  return ''
}

/** جعبهٔ «راهنمای قدم بعد» در تب فرایند — بدون متن توضیح اداری ترنزیشن */
export function getStudentNextStepHintBox(availableTransitions) {
  if (!availableTransitions?.length) return null
  const first = availableTransitions[0]
  const next = labelState(first?.to_state)
  if (availableTransitions.length === 1 && next && next !== '—') {
    return `پس از تکمیل کارهای همین مرحله، با دکمهٔ «ادامه و ثبت مرحله» به مرحلهٔ «${next}» می‌روید. پرداخت یا پیامک در صورت نیاز توسط سامانه انجام می‌شود.`
  }
  return 'پس از تکمیل کارهای همین مرحله، یکی از دکمه‌های ادامهٔ مسیر را بزنید. پرداخت یا پیامک در صورت نیاز توسط سامانه انجام می‌شود.'
}
