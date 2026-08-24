import { test } from 'node:test'
import assert from 'node:assert/strict'
import { filterSchemaForRole, filterSchemaForRoles, validateUnifiedAnswers } from './unifiedFormValidation.js'
import { operatorPortalRoles, roleMatchesAllowedList } from './userRoles.js'

const interviewResultSchema = {
  visible_to: ['interviewer', 'admissions_officer', 'admin'],
  fields: [
    { name: 'interview_result', label_fa: 'نتیجه مصاحبه', type: 'radio', required: true },
    { name: 'interviewer_notes', label_fa: 'یادداشت', type: 'textarea' },
  ],
}

test('roleMatchesAllowedList: faculty_1 matches interviewer', () => {
  assert.equal(roleMatchesAllowedList('faculty_1', ['interviewer', 'admin']), true)
  assert.equal(roleMatchesAllowedList('therapist', ['interviewer', 'admin']), false)
  assert.equal(roleMatchesAllowedList('interviewer', ['interviewer']), true)
})

test('filterSchemaForRole keeps interview result fields for faculty_1', () => {
  const out = filterSchemaForRole(interviewResultSchema, 'faculty_1')
  assert.equal(out.fields.length, 2)
  assert.equal(out.fields[0].name, 'interview_result')
})

test('filterSchemaForRole strips interview result fields for therapist', () => {
  const out = filterSchemaForRole(interviewResultSchema, 'therapist')
  assert.equal(out.fields.length, 0)
})

test('filterSchemaForRoles keeps interview fields for therapist+interviewer', () => {
  const hidden = filterSchemaForRoles(interviewResultSchema, ['therapist'])
  assert.equal(hidden.fields.length, 0)
  const shown = filterSchemaForRoles(interviewResultSchema, ['therapist', 'interviewer'])
  assert.equal(shown.fields.length, 2)
})

test('operatorPortalRoles of dual therapist+interviewer keeps interview schema', () => {
  const dual = { role: 'therapist', roles: ['therapist', 'interviewer'] }
  const out = filterSchemaForRoles(interviewResultSchema, operatorPortalRoles(dual))
  assert.equal(out.fields.length, 2)
})

test('validateUnifiedAnswers uses union of roles for required interview fields', () => {
  const hidden = validateUnifiedAnswers(interviewResultSchema, {}, { role: 'therapist' })
  assert.equal(hidden.ok, true)
  const dual = validateUnifiedAnswers(interviewResultSchema, {}, { roles: ['therapist', 'interviewer'] })
  assert.equal(dual.ok, false)
  assert.ok(dual.missing.length > 0)
})
