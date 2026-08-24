import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canStartProcess,
  canonicalAdmissionType,
  CONDITIONAL_THERAPY_TERM2_NOTICE_FA,
  isConditionalTherapyAdmission,
  isSingleCourseAdmission,
  resolvePrimaryInstanceId,
  shouldShowConditionalTherapyTerm2Notice,
  startTherapyAppliesToStudent,
} from './studentProcessAccess.js'

test('canonicalAdmissionType maps aliases', () => {
  assert.equal(canonicalAdmissionType('تک‌درس'), 'single_course')
  assert.equal(canonicalAdmissionType('result_single_course'), 'single_course')
  assert.equal(canonicalAdmissionType('مشروط به درمان'), 'conditional_therapy')
  assert.equal(canonicalAdmissionType('full'), 'full_admission')
})

test('single-course cannot start start_therapy', () => {
  const ctx = {
    studentProfile: { admission_type: 'single_course', extra_data: {} },
    activeProcesses: [],
    completedProcesses: [],
  }
  const res = canStartProcess('start_therapy', ctx)
  assert.equal(res.ok, false)
  assert.match(res.reasonFa, /تک‌درس/)
  assert.equal(startTherapyAppliesToStudent(ctx.studentProfile), false)
})

test('resolvePrimaryInstanceId skips start_therapy for single-course', () => {
  const therapyId = 'th-1'
  const profile = {
    course_type: 'introductory',
    admission_type: 'single_course',
    extra_data: { primary_instance_id: therapyId, admission_type: 'single_course' },
  }
  const instances = [
    { instance_id: therapyId, process_code: 'start_therapy', is_completed: false, is_cancelled: false, context_data: {} },
  ]
  assert.equal(resolvePrimaryInstanceId({ studentProfile: profile, instances, activeProcesses: instances }), null)
})

test('resolvePrimaryInstanceId skips forced start_therapy for conditional until opted in', () => {
  const therapyId = 'th-2'
  const profile = {
    course_type: 'introductory',
    admission_type: 'conditional_therapy',
    extra_data: { primary_instance_id: therapyId, admission_type: 'conditional_therapy' },
  }
  const instances = [
    {
      instance_id: therapyId,
      process_code: 'start_therapy',
      is_completed: false,
      is_cancelled: false,
      context_data: { source: 'after_introductory_registration_complete' },
    },
  ]
  assert.equal(isConditionalTherapyAdmission(profile), true)
  assert.equal(resolvePrimaryInstanceId({ studentProfile: profile, instances, activeProcesses: instances }), null)
})

test('resolvePrimaryInstanceId keeps start_therapy after conditional opt-in', () => {
  const therapyId = 'th-3'
  const profile = {
    course_type: 'introductory',
    admission_type: 'conditional_therapy',
    extra_data: {
      primary_instance_id: therapyId,
      admission_type: 'conditional_therapy',
      conditional_therapy_start_opted_in: true,
    },
  }
  const instances = [
    {
      instance_id: therapyId,
      process_code: 'start_therapy',
      is_completed: false,
      is_cancelled: false,
      context_data: { source: 'conditional_therapy_card_ensure' },
    },
  ]
  assert.equal(
    resolvePrimaryInstanceId({ studentProfile: profile, instances, activeProcesses: instances }),
    therapyId,
  )
})

test('isSingleCourseAdmission reads extra_data', () => {
  assert.equal(isSingleCourseAdmission({ extra_data: { admission_type: 'single_course' } }), true)
  assert.equal(isSingleCourseAdmission({ extra_data: { admission_type: 'full_admission' } }), false)
})

test('conditional therapy term2 notice after interview result', () => {
  assert.equal(
    CONDITIONAL_THERAPY_TERM2_NOTICE_FA,
    'به علت پذیرش مشروط به آغاز درمان آموزشی در دوره آشنایی پس از آغاز درمان آموزشی امکان ثبت نام در ترم دوم وجود دارد.',
  )
  assert.equal(
    shouldShowConditionalTherapyTerm2Notice({
      processCode: 'introductory_course_registration',
      currentState: 'result_conditional_therapy',
    }),
    true,
  )
  assert.equal(
    shouldShowConditionalTherapyTerm2Notice({
      studentProfile: { admission_type: 'conditional_therapy' },
      processCode: 'introductory_course_registration',
      currentState: 'registration_complete',
    }),
    true,
  )
  assert.equal(
    shouldShowConditionalTherapyTerm2Notice({
      studentProfile: { admission_type: 'full_admission' },
      processCode: 'introductory_course_registration',
      currentState: 'registration_complete',
    }),
    false,
  )
  assert.equal(
    shouldShowConditionalTherapyTerm2Notice({
      processCode: 'introductory_course_registration',
      currentState: 'application_submitted',
    }),
    false,
  )
})
