/**
 * فرایند introductory_course_registration: چهار ترنزیشن با یک trigger (interview_result_submitted)
 * و شرط‌های متفاوت. دکمهٔ UI باید interview_result را از to_state استنتاج کند.
 */
export const INTERVIEW_RESULT_BY_TO_STATE = {
  result_conditional_therapy: 'conditional_therapy',
  result_single_course: 'single_course',
  result_full_admission: 'full_admission',
  rejected: 'rejected',
}

/**
 * @param {Record<string, unknown>} payload
 * @param {string|undefined} toState — از transition.to_state (API)
 * @param {string|undefined} triggerEvent
 */
export function mergeInterviewBranchPayload(payload, toState, triggerEvent) {
  const out = { ...(payload && typeof payload === 'object' ? payload : {}) }
  if (triggerEvent !== 'interview_result_submitted') return out
  if (toState && INTERVIEW_RESULT_BY_TO_STATE[toState] && !out.interview_result) {
    out.interview_result = INTERVIEW_RESULT_BY_TO_STATE[toState]
  }
  return out
}
