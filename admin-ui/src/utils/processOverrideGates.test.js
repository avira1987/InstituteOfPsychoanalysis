import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canShowProcessRollback,
  OVERRIDE_ROLES,
} from './processRollbackUtils.js'
import {
  canShowProcessRestart,
  RESTART_STAFF_ROLES,
} from './processRestartUtils.js'

const historyTwo = [
  { from_state: null, to_state: 'a', trigger_event: 'start' },
  { from_state: 'a', to_state: 'b', trigger_event: 'go' },
]

const detail = {
  process_code: 'extra_session',
  current_state: 'b',
  is_cancelled: false,
  history: historyTwo,
}

test('OVERRIDE_ROLES excludes staff', () => {
  assert.equal(OVERRIDE_ROLES.includes('staff'), false)
  assert.equal(RESTART_STAFF_ROLES.includes('staff'), false)
  assert.equal(OVERRIDE_ROLES.includes('admin'), true)
  assert.equal(OVERRIDE_ROLES.includes('deputy_education'), true)
})

test('canShowProcessRollback: admin and deputy yes, staff no', () => {
  assert.equal(canShowProcessRollback(detail, { role: 'admin' }), true)
  assert.equal(canShowProcessRollback(detail, { role: 'deputy_education' }), true)
  assert.equal(
    canShowProcessRollback(detail, { role: 'staff', roles: ['staff'] }),
    false,
  )
  assert.equal(
    canShowProcessRollback(detail, { role: 'course_committee' }),
    false,
  )
})

test('canShowProcessRollback: multi-role with deputy yes', () => {
  assert.equal(
    canShowProcessRollback(detail, {
      role: 'staff',
      roles: ['staff', 'deputy_education'],
    }),
    true,
  )
})

test('canShowProcessRestart: override roles and student', () => {
  assert.equal(canShowProcessRestart(detail, { role: 'admin' }), true)
  assert.equal(canShowProcessRestart(detail, { role: 'deputy_education' }), true)
  assert.equal(canShowProcessRestart(detail, { role: 'student' }), true)
  assert.equal(
    canShowProcessRestart(detail, { role: 'staff', roles: ['staff'] }),
    false,
  )
})

test('canShowProcessRestart: blocked process codes', () => {
  const pay = { ...detail, process_code: 'session_payment' }
  assert.equal(canShowProcessRestart(pay, { role: 'admin' }), false)
})
