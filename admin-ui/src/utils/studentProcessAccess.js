/** قوانین سمت‌کاربر برای نمایش/شروع فرایند — هم‌راستا با مسیر آموزشی و نه کاتالوگ باز */

export const CORE_REGISTRATION_CODES = ['introductory_course_registration', 'comprehensive_course_registration']

/** فرایندهایی که تا وقتی ثبت‌نام دوره باز است نباید موازی شروع شوند */
const BLOCKED_WHILE_REGISTRATION_ACTIVE = new Set([
  'educational_leave', 'start_therapy', 'extra_session', 'session_payment',
  'therapy_changes', 'therapy_session_increase', 'therapy_session_reduction',
  'therapy_interruption', 'student_session_cancellation', 'student_supervision_cancellation', 'supervision_block_transition',
  'extra_supervision_session', 'supervision_session_increase', 'supervision_session_reduction',
  'supervision_interruption', 'supervisor_session_cancellation',
  'fee_determination', 'upgrade_to_ta', 'ta_track_change', 'upgrade_to_educational_therapist', 'internship_readiness_consultation',
])

/** نیاز به therapy_started روی پروفایل (به‌جز آغاز درمان) */
const REQUIRES_THERAPY_STARTED = new Set([
  'session_payment', 'extra_session', 'therapy_changes', 'therapy_session_increase',
  'therapy_session_reduction', 'therapy_interruption', 'student_session_cancellation',
  'therapy_completion', 'therapy_early_termination', 'fee_determination',
])

export function hasActiveRegistrationProcess(activeProcesses) {
  if (!activeProcesses?.length) return false
  return activeProcesses.some(p => CORE_REGISTRATION_CODES.includes(p.process_code))
}

/**
 * شناسهٔ نمونهٔ مسیر اصلی برای داشبورد — اگر primary خالی است ولی ثبت‌نام فعال دارد، همان را برمی‌گرداند.
 */
export function resolvePrimaryInstanceId({ studentProfile, instances, activeProcesses }) {
  const leaveActive = (instances || []).find(
    (i) => i.process_code === 'educational_leave' && !i.is_completed && !i.is_cancelled,
  )
  if (leaveActive?.instance_id) return leaveActive.instance_id

  const primaryRaw = studentProfile?.extra_data?.primary_instance_id
  if (primaryRaw) return primaryRaw

  const courseType = studentProfile?.course_type
  const expectedReg = courseType === 'comprehensive'
    ? 'comprehensive_course_registration'
    : courseType === 'introductory'
      ? 'introductory_course_registration'
      : null
  if (!expectedReg) return null

  const activeRegs = (activeProcesses || instances || []).filter(
    (p) => p.process_code === expectedReg && !p.is_completed && !p.is_cancelled,
  )
  if (activeRegs.length === 1) return activeRegs[0].instance_id
  return null
}

/**
 * @returns {{ ok: boolean, reasonFa: string }}
 */
function articleWritingPrerequisiteMet(studentProfile, activeProcesses) {
  const ex = studentProfile?.extra_data || {}
  if (ex.article_writing_completion_ticked || ex.thesis_defense_prerequisite_met) return true
  if (ex.thesis_defense_gate?.allowed === true) return true
  const art = (activeProcesses || []).find((p) => p.process_code === 'article_writing_completion')
  if (!art) return false
  if (art.is_completed) return true
  return ['completed_to_defense', 'instructor_eval_pending'].includes(art.current_state)
}

function upgradeToTaCompleted(studentProfile, activeProcesses) {
  const ex = studentProfile?.extra_data || {}
  if (ex.ta_registered === true || ex.is_teaching_assistant === true) return true
  const lms = ex.lms && typeof ex.lms === 'object' ? ex.lms : {}
  if (Array.isArray(lms.ta_active_tracks) && lms.ta_active_tracks.length > 0) return true
  return (activeProcesses || []).some(
    (p) => p.process_code === 'upgrade_to_ta' && p.is_completed,
  )
}

export function canStartProcess(processCode, { studentProfile, activeProcesses, completedProcesses }) {
  if (!studentProfile) {
    return { ok: false, reasonFa: 'پروفایل دانشجویی یافت نشد.' }
  }

  const blockingReg = hasActiveRegistrationProcess(activeProcesses)

  if (blockingReg && BLOCKED_WHILE_REGISTRATION_ACTIVE.has(processCode)) {
    return {
      ok: false,
      reasonFa: 'تا وقتی فرایند ثبت‌نام دوره باز است، از داشبورد همان مسیر را جلو ببرید؛ شروع فرایندهای دیگر در این مرحله فعال نیست.',
    }
  }

  if (processCode === 'full_education_leave') {
    const onFullLeave = studentProfile?.extra_data?.on_full_education_leave === true
    const activeFullLeave = (activeProcesses || []).find(
      (p) => p.process_code === 'full_education_leave' && !p.is_completed && !p.is_cancelled,
    )
    if (onFullLeave || activeFullLeave) {
      return {
        ok: false,
        reasonFa: 'مرخصی از کل آموزش در پروندهٔ شما فعال است — از همان فرایند یا «بازگشت به کل آموزش» استفاده کنید.',
      }
    }
  }

  if (processCode === 'return_to_full_education') {
    const onFullLeaveFlag = studentProfile?.extra_data?.on_full_education_leave === true
      || studentProfile?.extra_data?.gates?.next_term_registration_blocked === true
    const activeLeave = (activeProcesses || []).find((p) => p.process_code === 'full_education_leave')
    const completedLeave = (completedProcesses || []).some((p) => p.process_code === 'full_education_leave')
    const leaveApproved = activeLeave?.current_state === 'leave_approved' || activeLeave?.is_completed
    if (!onFullLeaveFlag && !completedLeave && !leaveApproved) {
      return {
        ok: false,
        reasonFa: 'این فرایند پس از تکمیل «مرخصی از کل آموزش» (فرایند ۵۹) در دسترس است.',
      }
    }
  }

  if (processCode === 'introductory_course_registration') {
    const gate = studentProfile.intro_registration_gate
    if (gate && gate.allowed === false) {
      return { ok: false, reasonFa: gate.reason_fa || 'ثبت‌نام دورهٔ آشنایی هنوز باز نشده است.' }
    }
    if (studentProfile.course_type !== 'introductory') {
      return { ok: false, reasonFa: 'این فرایند مخصوص دورهٔ آشنایی است.' }
    }
  }
  if (processCode === 'comprehensive_course_registration' && studentProfile.course_type !== 'comprehensive') {
    return { ok: false, reasonFa: 'این فرایند مخصوص دورهٔ جامع است.' }
  }

  const dup = activeProcesses.some(p => p.process_code === processCode)
  if (dup) {
    return { ok: false, reasonFa: 'برای این موضوع فرایند فعال دارید — از بخش «فرایندها» همان را ادامه دهید.' }
  }

  if (processCode === 'start_therapy' && studentProfile.therapy_started) {
    return { ok: false, reasonFa: 'درمان آموزشی در پروندهٔ شما قبلاً ثبت شده است.' }
  }

  const ex = studentProfile?.extra_data || {}
  const requiresTherapistUnlock = ex?.gates?.therapist_selection_requires_unlock === true
  const therapistUnlocked = ex?.lms?.access_flags?.therapist_selection_unlocked === true
  if (
    requiresTherapistUnlock
    && !therapistUnlocked
    && (processCode === 'start_therapy' || processCode === 'therapy_changes')
  ) {
    return {
      ok: false,
      reasonFa: 'انتخاب درمانگر پس از بررسی کمیته برای شما باز می‌شود. لطفاً پیام‌های پورتال را دنبال کنید.',
    }
  }

  if (REQUIRES_THERAPY_STARTED.has(processCode) && !studentProfile.therapy_started) {
    return {
      ok: false,
      reasonFa: 'این درخواست پس از «آغاز درمان آموزشی» در پروندهٔ شما در دسترس است.',
    }
  }

  if (processCode === 'thesis_defense_request' && !articleWritingPrerequisiteMet(studentProfile, activeProcesses)) {
    return {
      ok: false,
      reasonFa: 'پیش‌نیاز: تیک تکمیل پایان‌نامه توسط مدرس درس مقاله‌نویسی (فرایند ۶۹) باید ثبت شده باشد.',
    }
  }

  if (processCode === 'ta_track_change' && !upgradeToTaCompleted(studentProfile, activeProcesses)) {
    return {
      ok: false,
      reasonFa: 'این فرایند پس از تکمیل موفق «ارتقا به کمک‌مدرس» (فرایند ۴۷) در دسترس است.',
    }
  }

  return { ok: true, reasonFa: '' }
}

export function filterQuickActionCodes(codes, ctx) {
  return codes.filter(c => canStartProcess(c, ctx).ok)
}
