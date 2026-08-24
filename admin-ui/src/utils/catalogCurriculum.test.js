import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  curriculumFromCourse,
  curriculumPayload,
  emptyCurriculum,
  isUnenforcedSystemPrerequisite,
  normalizePrerequisiteCodes,
  togglePrerequisiteCode,
} from './catalogCurriculum.js'

test('curriculumPayload always sends prerequisite_codes list', () => {
  const body = curriculumPayload(emptyCurriculum())
  assert.deepEqual(body.prerequisite_codes, [])
  assert.deepEqual(body.system_prerequisite_codes, [])
  const withCodes = curriculumPayload({
    ...emptyCurriculum(),
    units: '3',
    prerequisite_codes: ['theory_psychoanalysis_1', ' theory_psychoanalysis_1 ', ''],
    system_prerequisite_codes: ['internship_started', 'internship_started', ''],
  })
  assert.deepEqual(withCodes.prerequisite_codes, ['theory_psychoanalysis_1'])
  assert.deepEqual(withCodes.system_prerequisite_codes, ['internship_started'])
  assert.equal(withCodes.units, 3)
  const flagged = curriculumPayload({
    ...emptyCurriculum(),
    single_course_allowed: true,
  })
  assert.equal(flagged.single_course_allowed, true)
})

test('togglePrerequisiteCode adds and removes', () => {
  const added = togglePrerequisiteCode([], 'theory_technique_1')
  assert.deepEqual(added, ['theory_technique_1'])
  assert.deepEqual(togglePrerequisiteCode(added, 'theory_technique_1'), [])
})

test('curriculumFromCourse copies structured prereqs', () => {
  const fields = curriculumFromCourse({
    units: 2,
    curriculum_term: 2,
    program_kind: 'introductory',
    prerequisite_codes: ['theory_psychoanalysis_1'],
    system_prerequisite_codes: ['internship_started'],
    prerequisite_notes: 'تئوری روانکاوی ۱',
  })
  assert.deepEqual(fields.prerequisite_codes, ['theory_psychoanalysis_1'])
  assert.deepEqual(fields.system_prerequisite_codes, ['internship_started'])
  assert.equal(fields.prerequisite_notes, 'تئوری روانکاوی ۱')
  assert.deepEqual(normalizePrerequisiteCodes(['a', 'a', '']), ['a'])
})

test('system prerequisites stay unenforced reminders', () => {
  assert.equal(isUnenforcedSystemPrerequisite('internship_started'), true)
  assert.equal(isUnenforcedSystemPrerequisite('clinical_hours_500'), true)
  assert.equal(isUnenforcedSystemPrerequisite('theory_psychoanalysis_1'), false)
})
