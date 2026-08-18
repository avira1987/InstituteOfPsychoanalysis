import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  courseValueRefs,
  isRosterOptionSelectableForCourse,
  markRosterOptionsForCourse,
  visibleRosterMembersForCourse,
} from './rosterCourseSelectability.js'

const catalog = [
  { value: 'theory_1', label_fa: 'تئوری ۱', aliases: ['تئوری (1)'] },
  { value: 'theory_2', label_fa: 'تئوری ۲' },
]

test('TA without grants is selectable as a track chart member', () => {
  const opt = { value: 'ta-1', label_fa: 'کمک‌مدرس الف', kind: 'teaching_assistant', authorized_courses: [] }
  assert.equal(isRosterOptionSelectableForCourse(opt, 'theory_1', { kind: 'teaching_assistant', catalogOptions: catalog }), true)
})

test('TA with matching grant is selectable', () => {
  const opt = {
    value: 'ta-1',
    label_fa: 'کمک‌مدرس الف',
    kind: 'teaching_assistant',
    authorized_courses: ['theory_1'],
  }
  assert.equal(isRosterOptionSelectableForCourse(opt, 'تئوری ۱', { kind: 'teaching_assistant', catalogOptions: catalog }), true)
  assert.equal(isRosterOptionSelectableForCourse(opt, 'theory_2', { kind: 'teaching_assistant', catalogOptions: catalog }), false)
})

test('instructor without grants is selectable as a track chart member', () => {
  const opt = { value: 'i1', label_fa: 'مدرس الف', kind: 'instructor', authorized_courses: [] }
  assert.equal(isRosterOptionSelectableForCourse(opt, 'theory_1', { kind: 'instructor', catalogOptions: catalog }), true)
})

test('instructor with matching grant is selectable', () => {
  const opt = {
    value: 'i1',
    label_fa: 'مدرس الف',
    kind: 'instructor',
    authorized_courses: ['theory_1'],
  }
  assert.equal(isRosterOptionSelectableForCourse(opt, 'تئوری ۱', { kind: 'instructor', catalogOptions: catalog }), true)
  assert.equal(isRosterOptionSelectableForCourse(opt, 'theory_2', { kind: 'instructor', catalogOptions: catalog }), false)
})

test('instructor_authorized_courses is read when authorized_courses is missing', () => {
  const opt = {
    value: 'i1',
    label_fa: 'مدرس الف',
    kind: 'instructor',
    instructor_authorized_courses: ['theory_1'],
  }
  assert.equal(isRosterOptionSelectableForCourse(opt, 'theory_1', { kind: 'instructor', catalogOptions: catalog }), true)
  assert.equal(isRosterOptionSelectableForCourse(opt, 'theory_2', { kind: 'instructor', catalogOptions: catalog }), false)
})

test('catalog aliases match course grants', () => {
  const refs = courseValueRefs('تئوری (1)', catalog)
  assert.equal(refs.has('theory_1'), true)
  assert.equal(refs.has('تئوری ۱'), true)
  const opt = { value: 'i1', label_fa: 'مدرس الف', authorized_courses: ['theory_1'] }
  assert.equal(isRosterOptionSelectableForCourse(opt, 'تئوری (1)', { catalogOptions: catalog }), true)
})

test('instructor with other-course grants is listed as disabled', () => {
  const options = [
    { value: 'i1', label_fa: 'مدرس مجاز', kind: 'instructor', authorized_courses: ['theory_1'] },
    { value: 'i2', label_fa: 'مدرس دیگر', kind: 'instructor', authorized_courses: ['theory_2'] },
  ]
  const marked = markRosterOptionsForCourse(options, 'theory_1', { kind: 'instructor', catalogOptions: catalog })
  assert.equal(marked.length, 2)
  const byId = Object.fromEntries(marked.map((o) => [o.value, o]))
  assert.equal(Boolean(byId.i1.disabled), false)
  assert.equal(byId.i2.disabled, true)
  assert.match(byId.i2.disabled_reason_fa, /مجاز/)
  assert.equal(marked[0].value, 'i1')
})

test('unauthorized track members stay visible but disabled', () => {
  const options = [
    { value: 'i1', label_fa: 'مدرس مجاز', authorized_courses: ['theory_1'] },
    { value: 'i2', label_fa: 'مدرس غیرمجاز', authorized_courses: ['theory_2'] },
  ]
  const marked = markRosterOptionsForCourse(options, 'theory_1', { kind: 'instructor', catalogOptions: catalog })
  assert.equal(marked.length, 2)
  const blocked = marked.find((o) => o.value === 'i2')
  assert.ok(blocked)
  assert.equal(blocked.disabled, true)
})

test('hideUnauthorized keeps ticked instructors and unticked chart members', () => {
  const options = [
    { value: 'i1', label_fa: 'مدرس مجاز', kind: 'instructor', authorized_courses: ['theory_1'] },
    { value: 'i2', label_fa: 'مدرس دیگر', kind: 'instructor', authorized_courses: ['theory_2'] },
    { value: 'i3', label_fa: 'مدرس بدون تیک', kind: 'instructor', authorized_courses: [] },
  ]
  const visible = markRosterOptionsForCourse(options, 'theory_1', {
    kind: 'instructor',
    catalogOptions: catalog,
    hideUnauthorized: true,
  })
  assert.deepEqual(visible.map((o) => o.value), ['i1', 'i3'])
})

test('hideUnauthorized without a selected course returns an empty list', () => {
  const options = [
    { value: 'i1', label_fa: 'مدرس الف', authorized_courses: ['theory_1'] },
  ]
  const visible = markRosterOptionsForCourse(options, '', {
    kind: 'instructor',
    catalogOptions: catalog,
    hideUnauthorized: true,
  })
  assert.deepEqual(visible, [])
})

test('new table row after selecting a course shows prep roster members', () => {
  const trackOptions = [
    { value: 'prep-1', label_fa: 'مدرس پیش‌آماده‌سازی', authorized_courses: ['theory_1'] },
    { value: 'prep-2', label_fa: 'مدرس بدون تیک', authorized_courses: [] },
    { value: 'other', label_fa: 'مدرس درس دیگر', authorized_courses: ['theory_2'] },
  ]
  const visible = visibleRosterMembersForCourse(trackOptions, 'تئوری ۱', {
    kind: 'instructor',
    catalogOptions: catalog,
  })
  assert.deepEqual(visible.map((o) => o.value), ['prep-1', 'prep-2'])
})

test('new table row without a course has no instructor options', () => {
  const trackOptions = [
    { value: 'prep-1', label_fa: 'مدرس پیش‌آماده‌سازی', authorized_courses: ['theory_1'] },
  ]
  assert.deepEqual(visibleRosterMembersForCourse(trackOptions, '', { catalogOptions: catalog }), [])
})
