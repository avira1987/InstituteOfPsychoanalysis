import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  catalogSelectValueFromRow,
  normalizeCourseTableInitialRows,
  shouldReplaceRowTrackFromCatalog,
  tracksAreEquivalent,
} from './courseTableRowNormalize.js'

const trackCol = {
  name: 'track',
  options: [
    { value: 'analytic_psychotherapy', label_fa: 'روان‌درمانی تحلیلی' },
    { value: 'comprehensive', label_fa: 'جامع' },
  ],
}

test('Persian track label is equivalent to catalog track code', () => {
  assert.equal(
    tracksAreEquivalent('روان‌درمانی تحلیلی', 'analytic_psychotherapy', trackCol),
    true,
  )
  assert.equal(
    tracksAreEquivalent('analytic_psychotherapy', 'روان‌درمانی تحلیلی', trackCol),
    true,
  )
  assert.equal(tracksAreEquivalent('جامع', 'comprehensive', trackCol), true)
  assert.equal(
    tracksAreEquivalent('روان‌درمانی تحلیلی', 'comprehensive', trackCol),
    false,
  )
})

test('re-entering step 4 with Persian track does not count as a track change', () => {
  const row = {
    course_name: 'تئوری روانکاوی ۱',
    track: 'روان‌درمانی تحلیلی',
    instructor: 'علی علوی',
    teaching_assistant: 'سارا',
  }
  assert.equal(
    shouldReplaceRowTrackFromCatalog(row, 'analytic_psychotherapy', trackCol),
    false,
  )
  assert.equal(
    shouldReplaceRowTrackFromCatalog(
      { ...row, track_code: 'analytic_psychotherapy' },
      'analytic_psychotherapy',
      trackCol,
    ),
    false,
  )
})

test('switching to a different catalog track does replace and can clear roster', () => {
  const row = {
    track: 'روان‌درمانی تحلیلی',
    track_code: 'analytic_psychotherapy',
    instructor: 'علی علوی',
  }
  assert.equal(shouldReplaceRowTrackFromCatalog(row, 'comprehensive', trackCol), true)
})

test('unknown new course has no expected track so roster is kept', () => {
  const row = { track: 'روان‌درمانی تحلیلی', instructor: 'مدرس جدید' }
  assert.equal(shouldReplaceRowTrackFromCatalog(row, '', trackCol), false)
})

test('step 5 text columns keep instructor name instead of UUID', () => {
  const uuid = '11111111-2222-4333-8444-555555555555'
  const rows = [
    {
      course_name: 'تئوری ۱',
      instructor: 'دکتر الف',
      instructor_id: uuid,
      teaching_assistant: 'کمک‌مدرس ب',
      teaching_assistant_id: '22222222-3333-4444-8555-666666666666',
    },
  ]
  const step5 = {
    columns: [
      { name: 'course_name', type: 'text', auto_fill: true },
      { name: 'instructor', type: 'text', auto_fill: true },
      { name: 'teaching_assistant', type: 'text', auto_fill: true },
    ],
  }
  const out = normalizeCourseTableInitialRows(step5, rows)
  assert.equal(out[0].instructor, 'دکتر الف')
  assert.equal(out[0].teaching_assistant, 'کمک‌مدرس ب')
})

test('step 4 select columns use instructor id and catalog course code', () => {
  const uuid = '11111111-2222-4333-8444-555555555555'
  const rows = [
    {
      course_name: 'تئوری ۱',
      instructor: 'دکتر الف',
      instructor_id: uuid,
    },
  ]
  const step4 = {
    columns: [
      {
        name: 'course_name',
        type: 'select',
        creatable: true,
        options: [{ value: 'theory_1', label_fa: 'تئوری ۱' }],
      },
      { name: 'instructor', type: 'select', creatable: true, searchable: true },
    ],
  }
  const out = normalizeCourseTableInitialRows(step4, rows)
  assert.equal(out[0].instructor, uuid)
  assert.equal(out[0].course_name, 'theory_1')
})

test('catalogSelectValueFromRow maps stored label to option value', () => {
  const catalog = [{ value: 'theory_1', label_fa: 'تئوری ۱' }]
  assert.equal(catalogSelectValueFromRow({ course_name: 'تئوری ۱' }, catalog), 'theory_1')
  assert.equal(catalogSelectValueFromRow({ course_name: 'theory_1' }, catalog), 'theory_1')
})
