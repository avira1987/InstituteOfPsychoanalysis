/** قوانین سمت‌کاربر برای نمایش/شروع فرایند — هم‌راستا با مسیر آموزشی و نه کاتالوگ باز */

export const CORE_REGISTRATION_CODES = ['introductory_course_registration', 'comprehensive_course_registration']

/** فرایندهایی که تا وقتی ثبت‌نام دوره باز است نباید موازی شروع شوند */
const BLOCKED_WHILE_REGISTRATION_ACTIVE = new Set([
  'educational_leave', 'start_therapy', 'extra_session', 'session_payment',
  'therapy_changes', 'therapy_session_increase', 'therapy_session_reduction',
  'therapy_interruption', 'student_session_cancellation', 'supervision_block_transition',
  'extra_supervision_session', 'supervision_session_increase', 'supervision_session_reduction',
  'fee_determination', 'upgrade_to_ta', 'internship_readiness_consultation',
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
 * @returns {{ ok: boolean, reasonFa: string }}
 */
export function canStartProcess(processCode, { studentProfile, activeProcesses }) {
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

  if (processCode === 'introductory_course_registration' && studentProfile.course_type !== 'introductory') {
    return { ok: false, reasonFa: 'این فرایند مخصوص دورهٔ آشنایی است.' }
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

  if (REQUIRES_THERAPY_STARTED.has(processCode) && !studentProfile.therapy_started) {
    return {
      ok: false,
      reasonFa: 'این درخواست پس از «آغاز درمان آموزشی» در پروندهٔ شما در دسترس است.',
    }
  }

  return { ok: true, reasonFa: '' }
}

export function filterQuickActionCodes(codes, ctx) {
  return codes.filter(c => canStartProcess(c, ctx).ok)
}
