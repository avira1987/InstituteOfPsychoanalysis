import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canSubmitInterviewResult,
  filterInterviewResultTransitions,
} from './interviewResultAccess.js'

const sara = {
  id: 'sara-1',
  role: 'faculty_1',
  roles: ['faculty_1'],
}

const interviewer = {
  id: 'iv-1',
  role: 'interviewer',
  roles: ['interviewer'],
}

const staff = {
  id: 'st-1',
  role: 'staff',
  roles: ['staff'],
}

const therapist = {
  id: 'th-1',
  role: 'therapist',
  roles: ['therapist'],
}

test('Sara / faculty_1 can submit when assigned to the slot', () => {
  assert.equal(
    canSubmitInterviewResult(sara, { interviewer_user_id: 'sara-1', slot_created_by: 'st-1' }),
    true,
  )
})

test('faculty_1 cannot submit another interviewer\'s slot', () => {
  assert.equal(
    canSubmitInterviewResult(sara, { interviewer_user_id: 'iv-1', slot_created_by: 'st-1' }),
    false,
  )
})

test('plain interviewer can submit own slot', () => {
  assert.equal(
    canSubmitInterviewResult(interviewer, { interviewer_user_id: 'iv-1' }),
    true,
  )
})

test('staff creator can submit even when an interviewer is assigned', () => {
  assert.equal(
    canSubmitInterviewResult(staff, { interviewer_user_id: 'iv-1', slot_created_by: 'st-1' }),
    true,
  )
})

test('therapist cannot submit interview result', () => {
  assert.equal(
    canSubmitInterviewResult(therapist, { interviewer_user_id: 'th-1' }),
    false,
  )
})

test('faculty_1 keeps interview_result transitions when assigned', () => {
  const transitions = [
    { trigger_event: 'interview_result_submitted', to_state: 'result_full_admission' },
    { trigger_event: 'interview_time_reached' },
  ]
  const out = filterInterviewResultTransitions(transitions, sara, { interviewer_user_id: 'sara-1' })
  assert.equal(out.length, 2)
})

test('faculty_1 loses interview_result transitions when not assigned', () => {
  const transitions = [
    { trigger_event: 'interview_result_submitted', to_state: 'result_full_admission' },
    { trigger_event: 'interview_time_reached' },
  ]
  const out = filterInterviewResultTransitions(transitions, sara, { interviewer_user_id: 'other' })
  assert.equal(out.some((t) => t.trigger_event === 'interview_result_submitted'), false)
  assert.equal(out.some((t) => t.trigger_event === 'interview_time_reached'), true)
})
