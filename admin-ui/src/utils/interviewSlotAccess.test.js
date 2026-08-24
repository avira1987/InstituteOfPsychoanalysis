import { test } from 'node:test'
import assert from 'node:assert/strict'
import { canManageInterviewSlots } from './interviewSlotAccess.js'

test('canManageInterviewSlots: string staff/admin only', () => {
  assert.equal(canManageInterviewSlots('staff'), true)
  assert.equal(canManageInterviewSlots('admin'), true)
  assert.equal(canManageInterviewSlots('internal_manager'), true)
  assert.equal(canManageInterviewSlots('therapist'), false)
  assert.equal(canManageInterviewSlots('interviewer'), false)
})

test('canManageInterviewSlots: dual therapist+staff can manage', () => {
  const dual = { role: 'therapist', roles: ['therapist', 'staff'] }
  assert.equal(canManageInterviewSlots(dual), true)
})

test('canManageInterviewSlots: plain therapist cannot manage', () => {
  assert.equal(canManageInterviewSlots({ role: 'therapist', roles: ['therapist'] }), false)
})
