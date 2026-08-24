import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  isStepOtpAlreadyVerified,
  CTX_STEP_OTP_VERIFIED_STATE,
} from './stepOtpVerified.js'

test('isStepOtpAlreadyVerified true when form flag set', () => {
  assert.equal(isStepOtpAlreadyVerified({ step_otp_verified: true }, {}, 'documents_upload'), true)
})

test('isStepOtpAlreadyVerified true when server stamp matches state', () => {
  const ctx = { [CTX_STEP_OTP_VERIFIED_STATE]: 'documents_upload' }
  assert.equal(isStepOtpAlreadyVerified({}, ctx, 'documents_upload'), true)
})

test('isStepOtpAlreadyVerified false when server stamp is other state', () => {
  const ctx = { [CTX_STEP_OTP_VERIFIED_STATE]: 'documents_incomplete' }
  assert.equal(isStepOtpAlreadyVerified({}, ctx, 'documents_upload'), false)
})

test('isStepOtpAlreadyVerified false when neither flag nor stamp', () => {
  assert.equal(isStepOtpAlreadyVerified({ digital_commitment: true }, {}, 'documents_upload'), false)
})

test('isStepOtpAlreadyVerified true when durable context flag set on later state', () => {
  assert.equal(
    isStepOtpAlreadyVerified({}, { step_otp_verified: true }, 'documents_incomplete'),
    true,
  )
})
