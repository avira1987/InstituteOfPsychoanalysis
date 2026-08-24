import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  hasCustomProcessPanel,
  usesGenericProcessPanel,
} from './processPanelRegistry.js'

test('educational_leave has no student custom panel and uses GenericProcessPanel', () => {
  assert.equal(hasCustomProcessPanel('educational_leave', 'student'), false)
  assert.equal(usesGenericProcessPanel('educational_leave', 'student'), true)
})

test('session_payment keeps its student custom panel', () => {
  assert.equal(hasCustomProcessPanel('session_payment', 'student'), true)
  assert.equal(usesGenericProcessPanel('session_payment', 'student'), false)
})

test('process without staff extras still uses the generic operator panel', () => {
  assert.equal(usesGenericProcessPanel('educational_leave', 'operator'), true)
  assert.equal(hasCustomProcessPanel('class_attendance', 'staff'), true)
})
