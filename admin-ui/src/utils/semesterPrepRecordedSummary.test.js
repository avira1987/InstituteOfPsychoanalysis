import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  hasRecordedPrepData,
  interviewPlanGroups,
  recordedSectionKeys,
  shouldShowPrepRecordedSummary,
  visibleCourseTables,
} from './semesterPrepRecordedSummary.js'

test('recordedSectionKeys only lists sections that have data', () => {
  assert.deepEqual(recordedSectionKeys({}), [])
  assert.equal(hasRecordedPrepData(null), false)
  assert.deepEqual(
    recordedSectionKeys({
      calendar: { fall_start_date: '2026-09-23' },
      tuition: {},
      courses: { courses_winter: [] },
      marketing: { marketing_notes: '' },
    }),
    ['calendar'],
  )
  assert.deepEqual(
    recordedSectionKeys({
      calendar: { fall_start_date: '2026-09-23' },
      tuition: { per_unit_cost_introductory: 1000 },
      license: { license_status: 'بدون تغییر' },
      courses: { courses_fall: [{ course_name: 'تئوری ۱' }] },
      marketing: { marketing_info_sent_to_manager: true },
      interviews: { interview_mode: 'حضوری' },
    }),
    ['calendar', 'tuition', 'license', 'courses', 'marketing', 'interviews'],
  )
})

test('hub summary is shown for started processes even when recorded is empty', () => {
  assert.equal(shouldShowPrepRecordedSummary({}), false)
  assert.equal(shouldShowPrepRecordedSummary({ active: true }), true)
  assert.equal(shouldShowPrepRecordedSummary({ completed_instance_id: 'abc' }), true)
  assert.equal(shouldShowPrepRecordedSummary({ instance_id: 'abc', active: false }), true)
})

test('visibleCourseTables skips empty arrays', () => {
  const tables = visibleCourseTables({
    courses_fall: [{ course_name: 'تئوری ۱' }],
    courses_winter: [],
    courses_finalized_fall: [{ course_name: 'تئوری ۱', day: 'شنبه' }],
  })
  assert.deepEqual(tables.map((t) => t.key), ['courses_fall', 'courses_finalized_fall'])
})

test('interviewPlanGroups keeps filled course types', () => {
  const groups = interviewPlanGroups({
    comprehensive: { interviewer_ids: ['دکتر رضایی'] },
    introductory: { interviewer_ids: [] },
  })
  assert.deepEqual(groups.map((g) => g.key), ['comprehensive'])
})
