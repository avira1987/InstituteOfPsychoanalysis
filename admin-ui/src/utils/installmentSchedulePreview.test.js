import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  addDaysIso,
  previewInstallmentPlan,
  splitInstallmentAmounts,
} from './installmentSchedulePreview.js'

test('split remainder on last installment', () => {
  assert.deepEqual(splitInstallmentAmounts(100, 3), [33, 33, 34])
  assert.deepEqual(splitInstallmentAmounts(1_200_000, 3), [400000, 400000, 400000])
})

test('addDaysIso does not shift timezone', () => {
  assert.equal(addDaysIso('2026-03-01', 25), '2026-03-26')
  assert.equal(addDaysIso('2026-03-01', 50), '2026-04-20')
})

test('preview dates match backend gap * (index-1)', () => {
  const plan = previewInstallmentPlan({
    totalRial: 1_200_000,
    paymentMethod: 'installment',
    count: 3,
    gapDays: 25,
    baseDueDate: '2026-03-01',
  })
  assert.equal(plan.length, 3)
  assert.deepEqual(plan.map((p) => p.due_at), ['2026-03-01', '2026-03-26', '2026-04-20'])
  assert.equal(plan.reduce((s, p) => s + p.amount_rial, 0), 1_200_000)
})
