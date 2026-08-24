import { test } from 'node:test'
import assert from 'node:assert/strict'
import { getUserRoles, operatorPortalRoles, orderedActorRoles, roleMatchesAllowedList, userHasAnyRole, userHasRole } from './userRoles.js'

test('getUserRoles falls back to primary role', () => {
  assert.deepEqual(getUserRoles({ role: 'therapist' }), ['therapist'])
})

test('getUserRoles injects primary when missing from list', () => {
  assert.deepEqual(getUserRoles({ role: 'therapist', roles: ['supervisor'] }), [
    'therapist',
    'supervisor',
  ])
})

test('userHasAnyRole matches membership', () => {
  const u = { role: 'therapist', roles: ['therapist', 'supervisor'] }
  assert.equal(userHasAnyRole(u, ['supervisor', 'finance']), true)
  assert.equal(userHasRole(u, 'finance', { adminBypass: false }), false)
})

test('faculty_1 implies interviewer and supervisor', () => {
  const u = { role: 'faculty_1', roles: ['faculty_1'] }
  assert.equal(userHasRole(u, 'interviewer', { adminBypass: false }), true)
  assert.equal(userHasRole(u, 'supervisor', { adminBypass: false }), true)
  assert.equal(userHasAnyRole(u, ['interviewer', 'staff'], { adminBypass: false }), true)
})

test('roleMatchesAllowedList expands faculty_1 to interviewer', () => {
  assert.equal(roleMatchesAllowedList('faculty_1', ['interviewer', 'admin']), true)
  assert.equal(roleMatchesAllowedList('internal_manager', ['staff']), true)
  assert.equal(roleMatchesAllowedList('therapist', ['interviewer']), false)
})

test('orderedActorRoles and operatorPortalRoles', () => {
  const faculty = { role: 'faculty_1', roles: ['faculty_1'] }
  const ordered = orderedActorRoles(faculty)
  assert.equal(ordered[0], 'faculty_1')
  assert.ok(ordered.includes('supervisor'))
  assert.ok(ordered.includes('interviewer'))
  const op = operatorPortalRoles(faculty)
  assert.ok(op.includes('faculty_1'))
  assert.ok(op.includes('interviewer'))

  const dual = { role: 'therapist', roles: ['therapist', 'interviewer'] }
  const dualOp = operatorPortalRoles(dual)
  assert.ok(dualOp.includes('therapist'))
  assert.ok(dualOp.includes('interviewer'))

  assert.deepEqual(operatorPortalRoles({ role: 'student', roles: ['student'] }), [])
})
