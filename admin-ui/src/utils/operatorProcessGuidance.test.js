import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildOperatorGuidance } from './operatorProcessGuidance.js'

const interviewDefinition = {
  process: { code: 'student_registration' },
  states: [{ code: 'interview', assigned_role: 'interviewer', metadata: {} }],
}

test('dual therapist+interviewer can act on interviewer assigned state', () => {
  const g = buildOperatorGuidance({
    definition: interviewDefinition,
    detail: { current_state: 'interview' },
    transitions: [],
    forms: [{ fields: [{}] }],
    user: { role: 'therapist', roles: ['therapist', 'interviewer'] },
  })
  assert.equal(g.canAct, true)
  assert.equal(g.waitingRoleLabelFa, '')
})

test('therapist-only waits on interviewer assigned state', () => {
  const g = buildOperatorGuidance({
    definition: interviewDefinition,
    detail: { current_state: 'interview' },
    transitions: [],
    forms: [],
    portalRole: 'therapist',
  })
  assert.equal(g.canAct, false)
  assert.ok(g.waitingRoleLabelFa)
})

test('faculty_1 can act on interviewer and supervisor, not semester-prep staff', () => {
  const interview = buildOperatorGuidance({
    definition: interviewDefinition,
    detail: { current_state: 'interview' },
    transitions: [],
    forms: [{ fields: [{}] }],
    user: { role: 'faculty_1', roles: ['faculty_1'] },
  })
  assert.equal(interview.canAct, true)

  const staffStep = buildOperatorGuidance({
    definition: {
      process: { code: 'fall_semester_preparation' },
      states: [{ code: 'calendar_entry', assigned_role: 'staff', metadata: {} }],
    },
    detail: { current_state: 'calendar_entry' },
    transitions: [],
    forms: [{ fields: [{}] }],
    user: { role: 'faculty_1', roles: ['faculty_1'] },
  })
  assert.equal(staffStep.canAct, false)

  const prepInterviews = buildOperatorGuidance({
    definition: {
      process: { code: 'fall_semester_preparation' },
      states: [{ code: 'interviewer_assignment', assigned_role: 'staff', metadata: {} }],
    },
    detail: { current_state: 'interviewer_assignment' },
    transitions: [],
    forms: [{ fields: [{}] }],
    user: { role: 'faculty_1', roles: ['faculty_1'] },
  })
  assert.equal(prepInterviews.canAct, false)
})
