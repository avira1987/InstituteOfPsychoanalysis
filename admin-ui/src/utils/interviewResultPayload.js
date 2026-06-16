import { INTERVIEW_RESULT_BY_TO_STATE, mergeInterviewBranchPayload } from './transitionInterviewPayload'

/**
 * @param {Record<string, unknown>} payload
 * @param {Record<string, unknown>} formValues
 * @param {string|undefined} toState
 * @param {string|undefined} triggerEvent
 */
export function mergeInterviewResultFormPayload(payload, formValues, toState, triggerEvent) {
  const out = mergeInterviewBranchPayload(payload, toState, triggerEvent)
  if (triggerEvent !== 'interview_result_submitted') return out

  const notes = (formValues?.interviewer_notes ?? '').toString().trim()
  if (notes) out.interviewer_notes = notes

  const ir = toState ? INTERVIEW_RESULT_BY_TO_STATE[toState] : null
  if (ir === 'conditional_therapy' || ir === 'full_admission') {
    out.admission_type = ir
  } else if (ir === 'single_course') {
    out.admission_type = 'single_course'
  }
  return out
}
