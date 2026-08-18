import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  documentReviewDecisionMessageFa,
  isDocumentReviewDecisionTrigger,
  operatorDocumentReviewToastFa,
} from './documentReviewStates.js'

test('documents_approved tells the operator this student review is finished', () => {
  const msg = documentReviewDecisionMessageFa({
    triggerEvent: 'documents_approved',
    studentCodeDisplay: '۱۴۰۳۱۲۳',
    toStateLabel: 'حساب کاربری ایجاد شد — ارسال اطلاعات ورود',
  })
  assert.match(msg, /کار تأیید مدارک دانشجو ۱۴۰۳۱۲۳ تمام شد/)
  assert.match(msg, /از صف بررسی خارج شد/)
  assert.match(msg, /وضعیت بعدی/)
})

test('documents_approved without student code still says this student is done', () => {
  const msg = documentReviewDecisionMessageFa({ triggerEvent: 'documents_approved' })
  assert.match(msg, /کار تأیید مدارک این دانشجو تمام شد/)
})

test('documents_rejected explains the file went back to the student', () => {
  const msg = documentReviewDecisionMessageFa({
    triggerEvent: 'documents_rejected',
    studentCodeDisplay: '۱۴۰۳۱۲۳',
  })
  assert.match(msg, /نواقص مدارک دانشجو ۱۴۰۳۱۲۳ ثبت شد/)
  assert.match(msg, /به دانشجو برگشت/)
})

test('operatorDocumentReviewToastFa only applies to document decisions', () => {
  assert.equal(isDocumentReviewDecisionTrigger('documents_approved'), true)
  assert.equal(isDocumentReviewDecisionTrigger('courses_selected'), false)
  assert.equal(
    operatorDocumentReviewToastFa('courses_selected', { toStateLabel: 'پرداخت' }),
    null,
  )
  const approved = operatorDocumentReviewToastFa('documents_approved', {
    studentCodeDisplay: '۱۴۰۳۱۲۳',
    toStateLabel: 'حساب کاربری ایجاد شد',
  })
  assert.match(approved, /کار تأیید مدارک دانشجو ۱۴۰۳۱۲۳ تمام شد/)
})
