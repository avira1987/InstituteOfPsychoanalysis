import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  SINGLE_COURSE_MISSING_HINT_FA,
  classifyCourseProgress,
  normalizeCourseCode,
  partitionByPrerequisites,
  resolveCheckboxListOptions,
  singleCourseAllowedCode,
  withStudentAdmissionContext,
} from './resolveCourseFieldOptions.js'

const REVERSE_TERM1 = [
  { value: 'theory_technique_1', label_fa: 'تئوری تکنیک‌ها ۱' },
  { value: 'theory_psychoanalysis_1', label_fa: 'تئوری روانکاوی ۱' },
]

test('single-course alias and student overlay hide technique 1', () => {
  const byAlias = resolveCheckboxListOptions(
    { source: 'available_courses_by_admission_type' },
    {
      interview_result: 'result_single_course',
      available_course_options: REVERSE_TERM1,
    },
  )
  assert.deepEqual(byAlias.options.map((o) => o.value), ['theory_psychoanalysis_1'])

  const byStudent = resolveCheckboxListOptions(
    { source: 'available_courses_by_admission_type' },
    withStudentAdmissionContext(
      {
        interview_result: 'full_admission',
        available_course_options: REVERSE_TERM1,
      },
      { extra_data: { admission_type: 'single_course' } },
    ),
  )
  assert.deepEqual(byStudent.options.map((o) => o.value), ['theory_psychoanalysis_1'])

  const nestedStaleFull = resolveCheckboxListOptions(
    { source: 'available_courses_by_admission_type' },
    {
      admission_type: 'single_course',
      interview_result: 'single_course',
      student: { admission_type: 'full_admission' },
      available_course_options: REVERSE_TERM1,
    },
  )
  assert.deepEqual(nestedStaleFull.options.map((o) => o.value), ['theory_psychoanalysis_1'])
})

test('single-course term 1 ignores alphabetical first item', () => {
  const resolved = resolveCheckboxListOptions(
    { source: 'available_courses_by_admission_type' },
    {
      admission_type: 'single_course',
      available_course_options: REVERSE_TERM1,
    },
  )
  assert.deepEqual(
    resolved.options.map((o) => o.value),
    ['theory_psychoanalysis_1'],
  )
  assert.equal(resolved.maxSelect, 1)
  assert.equal(resolved.hint, null)
})

test('single-course hides persian technique alias', () => {
  const resolved = resolveCheckboxListOptions(
    { source: 'available_courses_by_admission_type' },
    {
      admission_type: 'single_course',
      available_course_options: [
        { value: 'تئوری تکنیک یک', label_fa: 'تئوری تکنیک یک' },
        { value: 'تئوری روانکاوی یک', label_fa: 'تئوری روانکاوی یک' },
      ],
    },
  )
  assert.deepEqual(
    resolved.options.map((o) => o.value),
    ['theory_psychoanalysis_1'],
  )
  assert.equal(normalizeCourseCode('تئوری تکنیک یک'), 'theory_technique_1')
})

test('single-course term 2 picks psychoanalysis 2 not technique 2', () => {
  const resolved = resolveCheckboxListOptions(
    { source: 'filtered_courses_by_admission_type_and_prerequisites' },
    {
      admission_type: 'single_course',
      completed_courses: ['theory_psychoanalysis_1'],
      available_course_options: [
        {
          value: 'theory_technique_2',
          label_fa: 'تئوری تکنیک‌ها ۲',
          prerequisite_codes: ['theory_technique_1'],
        },
        {
          value: 'theory_psychoanalysis_2',
          label_fa: 'تئوری روانکاوی ۲',
          prerequisite_codes: ['theory_psychoanalysis_1'],
        },
      ],
    },
  )
  assert.deepEqual(
    resolved.options.map((o) => o.value),
    ['theory_psychoanalysis_2'],
  )
})

test('single-course missing allowed course has no index fallback', () => {
  const resolved = resolveCheckboxListOptions(
    { source: 'available_courses_by_admission_type' },
    {
      admission_type: 'single_course',
      available_course_options: [{ value: 'theory_technique_1', label_fa: 'تئوری تکنیک‌ها ۱' }],
    },
  )
  assert.deepEqual(resolved.options, [])
  assert.equal(resolved.hint, SINGLE_COURSE_MISSING_HINT_FA)
  assert.equal(singleCourseAllowedCode(1), 'theory_psychoanalysis_1')
  assert.equal(normalizeCourseCode('theory_1'), 'theory_psychoanalysis_1')
})

test('technique 2 blocked without pass even if enrolled', () => {
  const { passed } = classifyCourseProgress({
    lms: { enrolled_courses: ['theory_technique_1'] },
  })
  assert.equal(passed.has('theory_technique_1'), false)
  const { allowed, blocked } = partitionByPrerequisites(
    [
      {
        value: 'theory_technique_2',
        label_fa: 'تئوری تکنیک‌ها ۲',
        prerequisite_codes: ['theory_technique_1'],
      },
    ],
    passed,
    new Set(),
  )
  assert.equal(allowed.length, 0)
  assert.match(blocked[0].lock_reason_fa, /پیش‌نیاز پاس‌نشده/)
})

test('failed prereq becomes corequisite', () => {
  const { passed, failed } = classifyCourseProgress({
    lms: {
      enrolled_courses: [{ code: 'theory_psychoanalysis_1', pass_fail_status: 'مردود' }],
    },
  })
  assert.equal(failed.has('theory_psychoanalysis_1'), true)
  const { allowed } = partitionByPrerequisites(
    [
      {
        value: 'theory_psychoanalysis_2',
        label_fa: 'تئوری روانکاوی ۲',
        prerequisite_codes: ['theory_psychoanalysis_1'],
      },
    ],
    passed,
    failed,
  )
  const codes = allowed.map((o) => o.value)
  assert.ok(codes.includes('theory_psychoanalysis_2'))
  assert.ok(codes.includes('theory_psychoanalysis_1'))
})

test('unenforced system prerequisite codes do not block', () => {
  const { allowed, blocked } = partitionByPrerequisites(
    [
      {
        value: 'case_report_writing',
        label_fa: 'مقاله‌نویسی',
        prerequisite_codes: ['internship_started'],
        system_prerequisite_codes: ['clinical_hours_500'],
      },
    ],
    new Set(),
    new Set(),
  )
  assert.deepEqual(allowed.map((o) => o.value), ['case_report_writing'])
  assert.equal(blocked.length, 0)
})
