/**
 * فرایند comprehensive_course_registration: مصاحبهٔ ورود به دوره جامع.
 * سه ترنزیشن مجزا از حالت interview_completed:
 *   - interview_result_accepted                → پذیرش
 *   - interview_result_rejected                → رد قطعی
 *   - interview_result_rejected_with_suggestion → رد همراه با پیشنهاد
 * فرم ارزیابی محرمانه است (دلیل رد فقط در پورتال پذیرش ذخیره می‌شود و هرگز به دانشجو نمایش داده نمی‌شود).
 */

export const COMPREHENSIVE_EVAL_TRIGGERS = [
  'interview_result_accepted',
  'interview_result_rejected',
  'interview_result_rejected_with_suggestion',
]

/** trigger → مقدار فیلد result مطابق متادیتای فرم */
export const EVAL_RESULT_BY_TRIGGER = {
  interview_result_accepted: 'accepted',
  interview_result_rejected: 'rejected_definitive',
  interview_result_rejected_with_suggestion: 'rejected_with_suggestion',
}

export function isComprehensiveEvalTrigger(triggerEvent) {
  return COMPREHENSIVE_EVAL_TRIGGERS.includes(triggerEvent)
}

/**
 * اعتبارسنجی فرم ارزیابی برای trigger انتخاب‌شده.
 * @returns {string|null} پیام خطا یا null اگر معتبر باشد
 */
export function validateInterviewEvaluationForm(formValues, triggerEvent) {
  if (!isComprehensiveEvalTrigger(triggerEvent)) return null
  const values = formValues && typeof formValues === 'object' ? formValues : {}
  const notes = (values.evaluation_notes || '').trim()
  if (!notes) {
    return 'توضیحات ارزیابی الزامی است.'
  }
  const result = EVAL_RESULT_BY_TRIGGER[triggerEvent]
  if (result !== 'accepted') {
    const reason = (values.rejection_reason || '').trim()
    if (!reason) {
      return 'دلیل رد (محرمانه) الزامی است.'
    }
  }
  if (result === 'rejected_with_suggestion') {
    const suggestion = (values.suggestion_text || '').trim()
    if (!suggestion) {
      return 'متن پیشنهاد برای «رد همراه با پیشنهاد» الزامی است.'
    }
  }
  return null
}

/**
 * مرج مقادیر فرم ارزیابی در payload ترنزیشن.
 * مقدار result از روی trigger تعیین می‌شود تا با متادیتا هم‌خوان باشد.
 */
export function mergeInterviewEvaluationPayload(payload, formValues, triggerEvent) {
  const out = { ...(payload && typeof payload === 'object' ? payload : {}) }
  if (!isComprehensiveEvalTrigger(triggerEvent)) return out
  const values = formValues && typeof formValues === 'object' ? formValues : {}
  const result = EVAL_RESULT_BY_TRIGGER[triggerEvent]
  out.interview_evaluation_result = result
  out.interview_evaluation_notes = (values.evaluation_notes || '').trim()
  if (result !== 'accepted') {
    out.interview_rejection_reason = (values.rejection_reason || '').trim()
  }
  if (result === 'rejected_with_suggestion') {
    out.interview_suggestion_text = (values.suggestion_text || '').trim()
  }
  return out
}
