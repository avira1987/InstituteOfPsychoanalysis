/**
 * کدام فرایند پنل سفارشی دارد و کدام باید با GenericProcessPanel پیش برود.
 * پنل سفارشی فقط UX را غنی می‌کند؛ بدون آن هم فرم+انتقال+تاریخچه کافی است.
 */

/** فرایندهایی که در پورتال دانشجو یک *Panel اختصاصی دارند (علاوه بر فرم مرحله). */
export const STUDENT_CUSTOM_PROCESS_PANELS = new Set([
  'session_payment',
  'attendance_tracking',
  'therapy_completion',
  'therapy_session_reduction',
  'therapy_interruption',
  'student_session_cancellation',
  'student_supervision_cancellation',
  'supervisor_session_cancellation',
  'supervision_session_increase',
  'supervision_session_reduction',
  'supervision_interruption',
  'extra_supervision_session',
  'introductory_course_registration',
  'comprehensive_course_registration',
  'introductory_term_end',
  'comprehensive_term_end',
  'intro_second_semester_registration',
  'comprehensive_term_start',
  'lesson_start_per_term',
  'class_attendance',
  'student_non_registration',
  'student_instructor_evaluation',
  'violation_registration',
  'intern_bulk_patient_referral',
  'introductory_course_completion',
  'article_writing_completion',
  'ta_track_completion',
  'film_observation_course_completion',
  'live_therapy_observation_course_completion',
  'skills_course_completion',
  'theory_course_completion',
  'group_supervision_course_completion',
  'live_supervision_course_completion',
  'thesis_defense_request',
  'supervision_block_transition',
  'committees_review',
  'specialized_commission_review',
  'fee_determination',
  'internship_readiness_consultation',
  'upgrade_to_educational_therapist',
  'start_therapy',
  'return_to_full_education',
  'full_education_leave',
  'upgrade_to_ta',
  'ta_track_change',
  'ta_to_instructor_auto',
])

/**
 * فرایندهایی که در پورتال کارمند پنل اختصاصی *اضافه* دارند.
 * هستهٔ عمومی همیشه OperatorProcessInstancePanel / GenericProcessPanel است.
 */
export const STAFF_CUSTOM_PROCESS_PANELS = new Set([
  'ta_track_completion',
  'ta_track_change',
  'ta_to_instructor_auto',
  'supervision_50h_completion',
  'ta_essay_upload',
  'mentor_private_sessions',
  'ta_conceptual_questions',
  'article_writing_completion',
  'live_supervision_course_completion',
  'class_attendance',
  'class_session_cancellation',
  'live_therapy_observation_ta_attendance_completion',
  'film_observation_ta_attendance_completion',
  'film_observation_course_completion',
  'live_therapy_observation_course_completion',
  'skills_course_completion',
  'theory_course_completion',
  'group_supervision_course_completion',
  'introductory_course_registration',
])

export function hasCustomProcessPanel(processCode, audience = 'student') {
  const code = String(processCode || '')
  if (audience === 'operator' || audience === 'staff') {
    return STAFF_CUSTOM_PROCESS_PANELS.has(code)
  }
  return STUDENT_CUSTOM_PROCESS_PANELS.has(code)
}

/** اگر پنل سفارشی نبود، GenericProcessPanel منبع حقیقت UI است. */
export function usesGenericProcessPanel(processCode, audience = 'student') {
  return !hasCustomProcessPanel(processCode, audience)
}
