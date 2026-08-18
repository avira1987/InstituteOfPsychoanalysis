import { COMPREHENSIVE_EVAL_TRIGGERS } from './interviewEvaluationPayload.js'
import { userHasAnyRole, userHasRole } from './userRoles.js'

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
 * faculty_1 (هیئت علمی) معادل interviewer است.
 */
export function canSubmitInterviewResult(user, contextData) {
  if (!user) return false
  if (userHasRole(user, 'admin', { adminBypass: false })) return true
  if (!userHasAnyRole(user, ['interviewer', 'staff'], { adminBypass: false })) return false

  const uid = String(user.id)
  const assigned = contextData?.interviewer_user_id
  if (assigned && String(assigned) === uid) return true

  const creator = contextData?.slot_created_by
  if (creator && String(creator) === uid) {
    if (userHasRole(user, 'staff', { adminBypass: false })) return true
    return !assigned
  }

  return false
}

export function filterInterviewResultTransitions(transitions, user, contextData) {
  if (!transitions?.length) return transitions || []
  if (canSubmitInterviewResult(user, contextData)) return transitions
  return transitions.filter((t) => !isInterviewResultTrigger(t.trigger_event))
}
