import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isPreviousStepReviewEnabled } from './studentProcessStepReview.js'

test('isPreviousStepReviewEnabled is off by default', () => {
  assert.equal(isPreviousStepReviewEnabled(undefined), false)
  assert.equal(isPreviousStepReviewEnabled(null), false)
  assert.equal(isPreviousStepReviewEnabled({}), false)
  assert.equal(isPreviousStepReviewEnabled({ allow_previous_step_review: false }), false)
  assert.equal(isPreviousStepReviewEnabled({ allow_previous_step_review: 'true' }), false)
  assert.equal(isPreviousStepReviewEnabled({ allow_previous_step_review: 1 }), false)
})

test('isPreviousStepReviewEnabled is on only for true', () => {
  assert.equal(isPreviousStepReviewEnabled({ allow_previous_step_review: true }), true)
})
