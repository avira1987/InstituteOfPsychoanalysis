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
 * هم‌راستا با app/core/interview_result_access.py
 */
export function canSubmitInterviewResult(user, contextData) {
  if (!user) return false
  if (user.role === 'admin') return true
  if (!['interviewer', 'staff'].includes(user.role)) return false

  const uid = String(user.id)
  const assigned = contextData?.interviewer_user_id
  if (assigned && String(assigned) === uid) return true

  const creator = contextData?.slot_created_by
  if (creator && String(creator) === uid) {
    if (user.role === 'interviewer') {
      return !assigned
    }
    return true
  }

  return false
}

export function filterInterviewResultTransitions(transitions, user, contextData) {
  if (!transitions?.length) return transitions || []
  if (canSubmitInterviewResult(user, contextData)) return transitions
  return transitions.filter((t) => !isInterviewResultTrigger(t.trigger_event))
}
