import { test } from 'node:test'
import assert from 'node:assert/strict'
import { getUserRoles, userHasAnyRole, userHasRole } from './userRoles.js'

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
