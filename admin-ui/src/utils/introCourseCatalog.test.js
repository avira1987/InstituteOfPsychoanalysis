import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatCourseInstructorFa,
  formatCourseOptionSpecs,
  formatCourseScheduleFa,
  optionsFromContext,
  tuitionQuoteFromContext,
} from './introCourseCatalog.js'

test('formatCourseScheduleFa joins day and time', () => {
  assert.equal(
    formatCourseScheduleFa({ day: 'شنبه', time_text: '۱۰:۰۰' }),
    'شنبه ۱۰:۰۰',
  )
  assert.equal(formatCourseScheduleFa({ time: '09:00-11:00' }), '09:00-11:00')
  assert.equal(formatCourseScheduleFa({ day: '  ' }), '')
})

test('formatCourseInstructorFa reads published instructor fields', () => {
  assert.equal(formatCourseInstructorFa({ instructor_name: 'دکتر الف' }), 'دکتر الف')
  assert.equal(formatCourseInstructorFa({ instructor: 'دکتر ب' }), 'دکتر ب')
  assert.equal(formatCourseInstructorFa({}), '')
})

test('formatCourseOptionSpecs shows hour and instructor for course selection', () => {
  assert.equal(
    formatCourseOptionSpecs({
      day: 'شنبه',
      time_text: '۱۰:۰۰',
      instructor_name: 'دکتر الف',
    }),
    'مشخصات: ساعت: شنبه ۱۰:۰۰  ·  مدرس: دکتر الف',
  )
  assert.equal(
    formatCourseOptionSpecs({ instructor_name: 'دکتر ب' }),
    'مشخصات: مدرس: دکتر ب',
  )
  assert.equal(formatCourseOptionSpecs({ label_fa: 'تئوری ۱', units: 2 }), '')
})

test('optionsFromContext keeps schedule and instructor for term-1 form', () => {
  const options = optionsFromContext({
    available_course_options: [
      {
        value: 'theory_psychoanalysis_1',
        label_fa: 'تئوری روانکاوی ۱',
        day: 'شنبه',
        time_text: '۱۰:۰۰',
        instructor_name: 'دکتر الف',
        units: 2,
      },
    ],
  })
  assert.equal(options.length, 1)
  assert.equal(options[0].day, 'شنبه')
  assert.equal(options[0].time_text, '۱۰:۰۰')
  assert.equal(options[0].instructor_name, 'دکتر الف')
  assert.match(formatCourseOptionSpecs(options[0]), /ساعت: شنبه ۱۰:۰۰/)
  assert.match(formatCourseOptionSpecs(options[0]), /مدرس: دکتر الف/)
})

test('tuitionQuoteFromContext sums seven intro units at panel rate', () => {
  const quote = tuitionQuoteFromContext({
    tuition_total_rial: 70000,
    tuition_lines: [
      { course_code: 'theory_psychoanalysis_1', units: 2, per_unit_cost_rial: 10000, line_amount_rial: 20000 },
      { course_code: 'theory_technique_1', units: 3, per_unit_cost_rial: 10000, line_amount_rial: 30000 },
      { course_code: 'skills_practice_1', units: 2, per_unit_cost_rial: 10000, line_amount_rial: 20000 },
    ],
  })
  assert.equal(quote.totalUnits, 7)
  assert.equal(quote.totalRial, 70000)
  assert.notEqual(quote.totalRial, 52000)
})

test('optionsFromContext accepts alternate time/instructor keys from prep rows', () => {
  const options = optionsFromContext({
    lms: {
      available_course_options: [
        {
          value: 'skills_1',
          label_fa: 'مهارت ۱',
          day: 'یکشنبه',
          time: '14:00',
          instructor: 'دکتر ب',
        },
      ],
    },
  })
  assert.equal(options[0].time_text, '14:00')
  assert.equal(options[0].instructor_name, 'دکتر ب')
  assert.equal(
    formatCourseOptionSpecs(options[0]),
    'مشخصات: ساعت: یکشنبه 14:00  ·  مدرس: دکتر ب',
  )
})
