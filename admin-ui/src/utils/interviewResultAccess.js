import { COMPREHENSIVE_EVAL_TRIGGERS } from './interviewEvaluationPayload'

export const INTERVIEW_RESULT_TRIGGERS = [
  'interview_result_submitted',
  ...COMPREHENSIVE_EVAL_TRIGGERS,
]

export function isInterviewResultTrigger(triggerEvent) {
  return INTERVIEW_RESULT_TRIGGERS.includes(triggerEvent)
}

/**
 * آیا کاربر جاری مجاز به ثبت نتیجهٔ مصاحبه برای این پرونده است؟
 * (ادمین همیشه؛ مصاحبه‌گر فقط وقتی interviewer_user_id با خودش یکی باشد
 *  یا اسلات بدون مصاحبه‌گر اختصاصی ولی توسط خودش ساخته شده باشد — منطق سرور مرجع است.)
 */
export function canSubmitInterviewResult(user, contextData) {
  if (!user) return false
  if (user.role === 'admin') return true
  if (user.role !== 'interviewer') return false
  const assigned = contextData?.interviewer_user_id
  if (assigned) return String(assigned) === String(user.id)
  return false
}

export function filterInterviewResultTransitions(transitions, user, contextData) {
  if (!transitions?.length) return transitions || []
  if (canSubmitInterviewResult(user, contextData)) return transitions
  return transitions.filter((t) => !isInterviewResultTrigger(t.trigger_event))
}
