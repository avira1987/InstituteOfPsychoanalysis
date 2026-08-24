import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  anyPortalRoleCanActOnState,
  effectivePortalRole,
  formRolesForUser,
  portalRoleCanActOnState,
} from './portalRoleAccess.js'

test('faculty_1 can act on interviewer and supervisor assigned roles', () => {
  assert.equal(portalRoleCanActOnState('faculty_1', 'interviewer'), true)
  assert.equal(portalRoleCanActOnState('faculty_1', 'supervisor'), true)
  assert.equal(portalRoleCanActOnState('faculty_1', 'staff'), false)
})

test('anyPortalRoleCanActOnState unions dual therapist+interviewer', () => {
  assert.equal(anyPortalRoleCanActOnState(['therapist'], 'interviewer'), false)
  assert.equal(
    anyPortalRoleCanActOnState(['therapist', 'interviewer'], 'interviewer'),
    true,
  )
  assert.equal(anyPortalRoleCanActOnState(['faculty_1', 'supervisor'], 'staff'), false)
})

test('effectivePortalRole picks interviewer for dual-role on interview state', () => {
  const dual = { role: 'therapist', roles: ['therapist', 'interviewer'] }
  assert.equal(effectivePortalRole(dual, 'interviewer'), 'interviewer')
  assert.equal(effectivePortalRole(dual, 'therapist'), 'therapist')
})

test('formRolesForUser student empty then fallback', () => {
  assert.deepEqual(formRolesForUser({ role: 'student', roles: ['student'] }, 'student'), ['student'])
  const dual = { role: 'therapist', roles: ['therapist', 'interviewer'] }
  const roles = formRolesForUser(dual)
  assert.ok(roles.includes('therapist'))
  assert.ok(roles.includes('interviewer'))
})
