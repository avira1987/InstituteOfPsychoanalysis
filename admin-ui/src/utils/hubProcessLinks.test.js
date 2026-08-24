import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  HUB_VIOLATION,
  HUB_REFERRAL,
  studentProcessInstanceHref,
  violationCommitteeHref,
  violationCommitteeKind,
  patientReferralCommitteeHref,
} from './hubProcessLinks.js'

test('student process instance href includes tab and codes', () => {
  const href = studentProcessInstanceHref({
    processCode: HUB_VIOLATION,
    instanceId: 'abc',
  })
  assert.ok(href.includes('/panel/portal/student'))
  assert.ok(href.includes('tab=processes'))
  assert.ok(href.includes('process_code=violation_registration'))
  assert.ok(href.includes('instance_id=abc'))
})

test('education referral goes to education committee', () => {
  assert.equal(violationCommitteeKind('referred_to_education_committee'), 'education')
  const href = violationCommitteeHref({
    instanceId: 'v1',
    studentId: 's1',
    stateCode: 'referred_to_education_committee',
  })
  assert.ok(href.includes('/panel/portal/committee/education'))
  assert.ok(href.includes('instance_id=v1'))
})

test('default violation inbox is supervision committee', () => {
  assert.equal(
    violationCommitteeKind('review_status_set', 'monitoring_committee_officer'),
    'supervision',
  )
  const href = violationCommitteeHref({
    instanceId: 'v2',
    stateCode: 'verdict_issued',
    roleCode: 'supervision_committee',
  })
  assert.ok(href.includes('/panel/portal/committee/supervision'))
  assert.ok(href.includes('tab=reviews'))
})

test('patient_referral hub goes to supervision committee', () => {
  const href = patientReferralCommitteeHref({ instanceId: 'pr-1', studentId: 's1' })
  assert.ok(href.includes('/panel/portal/committee/supervision'))
  assert.ok(href.includes('process_code=patient_referral'))
  assert.ok(href.includes('instance_id=pr-1'))
  assert.equal(HUB_REFERRAL, 'patient_referral')
})
