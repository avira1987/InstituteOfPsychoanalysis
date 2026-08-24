import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  effectiveSemesterPrepAssignedRole,
  isSemesterPrepInternalManagerState,
  semesterPrepResponsibleRoleLabelFa,
} from './semesterPrepRoles.js'

test('last prep interview step is labeled internal manager', () => {
  assert.equal(
    isSemesterPrepInternalManagerState('fall_semester_preparation', 'interviewer_assignment'),
    true,
  )
  assert.equal(
    isSemesterPrepInternalManagerState('winter_semester_preparation', 'interview_scheduling'),
    true,
  )
  assert.equal(
    isSemesterPrepInternalManagerState('fall_semester_preparation', 'tuition_entry'),
    false,
  )
  assert.equal(
    effectiveSemesterPrepAssignedRole(
      'fall_semester_preparation',
      'interviewer_assignment',
      'deputy_education_director',
    ),
    'staff',
  )
  const label = semesterPrepResponsibleRoleLabelFa(
    'fall_semester_preparation',
    'interview_scheduling',
    'deputy_education_director',
  )
  assert.match(label, /مدیر داخلی/)
  assert.doesNotMatch(label, /معاون/)
})
