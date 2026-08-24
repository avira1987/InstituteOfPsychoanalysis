import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyInstallmentPolicyToForms,
  isInstallmentEnabled,
} from './installmentPolicyForms.js'

test('missing flag keeps installments enabled', () => {
  assert.equal(isInstallmentEnabled(null), true)
  assert.equal(isInstallmentEnabled({}), true)
})

test('disabled policy removes installment option and count field', () => {
  const forms = [
    {
      fields: [
        {
          name: 'payment_method',
          options: [
            { value: 'cash', label_fa: 'نقدی' },
            { value: 'installment', label_fa: 'اقساط' },
          ],
        },
        { name: 'installment_count', options: [2, 3] },
      ],
    },
  ]
  const out = applyInstallmentPolicyToForms(forms, { installment_enabled: false }, {})
  assert.deepEqual(
    out[0].fields[0].options.map((o) => o.value),
    ['cash'],
  )
  assert.equal(out[0].fields.some((f) => f.name === 'installment_count'), false)
  assert.equal(forms[0].fields[0].options.length, 2)
})

test('already on installment keeps options when globally disabled', () => {
  const forms = [
    {
      fields: [
        {
          name: 'payment_method',
          options: [{ value: 'cash' }, { value: 'installment' }],
        },
        { name: 'installment_count' },
      ],
    },
  ]
  const out = applyInstallmentPolicyToForms(
    forms,
    { installment_enabled: false },
    { payment_method: 'installment' },
  )
  assert.equal(out[0].fields.some((f) => f.name === 'installment_count'), true)
  assert.equal(
    out[0].fields[0].options.some((o) => o.value === 'installment'),
    true,
  )
})
