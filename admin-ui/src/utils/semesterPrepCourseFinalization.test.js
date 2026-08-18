import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyCourseFinalizationPrefill,
  isSemesterPrepStepFormSubmitted,
  syncCoursesFinalizedFromDraft,
} from './semesterPrepCourseFinalization.js'

test('step 5 always takes course list and hours from edited step 4', () => {
  const draft = [
    {
      course_name: 'تئوری ۱ ویرایش‌شده',
      course_code: 'theory_1',
      proposed_day: 'یکشنبه',
      proposed_time: '19:00',
      instructor: 'دکتر جدید',
    },
    {
      course_name: 'درس تازه‌اضافه‌شده',
      proposed_day: 'سه‌شنبه',
      proposed_time: '16:00',
      instructor: 'دکتر ج',
    },
  ]
  const staleFinalized = [
    {
      course_name: 'تئوری ۱',
      course_code: 'theory_1',
      day: 'شنبه',
      time: '18:00',
      instructor: 'دکتر الف',
      classroom_location: 'کلاس ۱',
      instructor_coordinated: true,
    },
    {
      course_name: 'درس حذف‌شده',
      day: 'دوشنبه',
      time: '10:00',
      classroom_location: 'کلاس قدیم',
      instructor_coordinated: true,
    },
  ]
  const synced = syncCoursesFinalizedFromDraft(draft, staleFinalized)
  assert.equal(synced.length, 2)
  assert.equal(synced[0].course_name, 'تئوری ۱ ویرایش‌شده')
  assert.equal(synced[0].day, 'یکشنبه')
  assert.equal(synced[0].time, '19:00')
  assert.equal(synced[0].instructor, 'دکتر جدید')
  assert.equal(synced[0].classroom_location, 'کلاس ۱')
  assert.equal(synced[0].instructor_coordinated, true)
  assert.equal(synced[1].course_name, 'درس تازه‌اضافه‌شده')
  assert.equal(synced[1].day, 'سه‌شنبه')
  assert.equal(synced[1].classroom_location, '')
  assert.equal(synced[1].instructor_coordinated, false)
})

test('applyCourseFinalizationPrefill overwrites stale finalized tables from draft', () => {
  const init = {
    courses_finalized_fall: [
      { course_name: 'درس قدیمی', day: 'شنبه', time: '08:00', instructor: 'قدیمی' },
    ],
  }
  const ctx = {
    courses_fall: [
      {
        course_name: 'درس جدید',
        proposed_day: 'چهارشنبه',
        proposed_time: '20:00',
        instructor: 'جدید',
      },
    ],
    courses_winter: [
      {
        course_name: 'عملی زمستان',
        proposed_day: 'پنجشنبه',
        proposed_time: '17:30',
        instructor: 'دکتر ب',
      },
    ],
  }
  applyCourseFinalizationPrefill(init, ctx, 'fall_semester_preparation')
  assert.equal(init.courses_finalized_fall[0].course_name, 'درس جدید')
  assert.equal(init.courses_finalized_fall[0].day, 'چهارشنبه')
  assert.equal(init.courses_finalized_fall[0].time, '20:00')
  assert.equal(init.courses_finalized_winter[0].course_name, 'عملی زمستان')
  assert.equal(init.courses_finalized_winter[0].day, 'پنجشنبه')
})

test('blank placeholder rows from step 4 are not copied into step 5', () => {
  const draft = [
    {
      course_name: 'تئوری ۱',
      proposed_day: 'شنبه',
      proposed_time: '18:00',
      instructor: 'دکتر الف',
    },
    {
      course_name: '',
      track: '',
      proposed_day: '',
      proposed_time: '',
      instructor: '',
    },
  ]
  const synced = syncCoursesFinalizedFromDraft(draft, [])
  assert.equal(synced.length, 1)
  assert.equal(synced[0].course_name, 'تئوری ۱')
  assert.equal(synced[0].instructor, 'دکتر الف')
})

test('next-step button lights up after a single local save even if context reload lags', () => {
  assert.equal(isSemesterPrepStepFormSubmitted({}, 'course_list_creation'), false)
  assert.equal(
    isSemesterPrepStepFormSubmitted({}, 'course_list_creation', 'course_list_creation'),
    true,
  )
  assert.equal(
    isSemesterPrepStepFormSubmitted(
      { __student_forms_submitted_states: { course_finalization: '2026-08-16T10:00:00Z' } },
      'course_finalization',
    ),
    true,
  )
  assert.equal(
    isSemesterPrepStepFormSubmitted(
      { __student_forms_submitted_states: { course_list_creation: '2026-08-16T10:00:00Z' } },
      'course_finalization',
    ),
    false,
  )
})
