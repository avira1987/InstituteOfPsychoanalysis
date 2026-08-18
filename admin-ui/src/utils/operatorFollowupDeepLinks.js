/**
 * مقصد کلیک از «صندوق پیگیری اپراتور» برای مدیر اصلی —
 * مسیر نقش‌محور به تب مناسب + instance_id برای باز شدن خودکار کارت فرایند.
 */
import { committeeKindForAssignedRole, getCommitteeKindPath } from './portalCommitteeKinds'
import { getStaffLanePath, staffLaneForAssignedRole } from './portalStaffLanes'

const FALLBACK_HINT = 'ردیابی دانشجو (همه نقش‌ها)'

const SEMESTER_PREP_CODES = new Set(['fall_semester_preparation', 'winter_semester_preparation'])

const STUDENT_LIKE_ROLES = new Set(['student', 'applicant'])

function isStudentLikeRole(code) {
  return STUDENT_LIKE_ROLES.has((code || '').toLowerCase())
}

function studentPortalProcessesHref(params = {}) {
  return `/panel/portal/student${qs({ tab: 'processes', ...params })}`
}

const DEPUTY_PREP_ROLES = new Set([
  'deputy_education',
  'deputy_education_director',
])

const COURSE_COMMITTEE_PREP_ROLES = new Set([
  'course_committee',
  'course_committee_executive',
  'course_committee_scientific',
  'scientific_officer_course_committee',
])

function workbenchHref(processCode) {
  return `/panel/semester-prep/workbench?process_code=${encodeURIComponent(processCode)}`
}

/** شناسهٔ نمونه — در برخی لیست‌ها `id` و در برخی `instance_id` است. */
export function resolvePendingInstanceId(item) {
  if (!item || typeof item !== 'object') return null
  return item.instance_id || item.id || null
}

/**
 * مقصد کلیک از «وظایف منتظر» یا کارتابل — با پشتیبانی از آماده‌سازی ترم.
 * @param {FollowupItem & { current_state?: string }} item
 */
export function getPendingTaskDestination(item) {
  const instanceId = resolvePendingInstanceId(item)
  const stateCode = (item.state_code || item.current_state || '').toLowerCase()
  return getOperatorFollowupDestination({
    kind: item.kind || 'process',
    instance_id: instanceId,
    student_id: item.student_id,
    responsible_role_code: item.responsible_role_code,
    process_code: (item.process_code || '').toLowerCase(),
    state_code: stateCode,
    assignment_id: item.assignment_id,
  })
}

export function isSemesterPrepWorkbenchDestination(href) {
  return typeof href === 'string' && href.includes('/panel/semester-prep/workbench')
}

function qs(params) {
  const u = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') u.set(k, String(v))
  })
  const s = u.toString()
  return s ? `?${s}` : ''
}

function staffHref(params, laneId) {
  const lane = laneId || 'admissions'
  return `${getStaffLanePath(lane)}${qs(params)}`
}

function committeeHref(params, roleCode) {
  const kind = committeeKindForAssignedRole(roleCode)
  return `${getCommitteeKindPath(kind)}${qs(params)}`
}

/** @typedef {{ kind: string, instance_id?: string, student_id?: string, assignment_id?: string, responsible_role_code?: string, process_code?: string, state_code?: string }} FollowupItem */

/**
 * @param {FollowupItem} item
 * @returns {{ href: string, hintFa: string }}
 */
export function getOperatorFollowupDestination(item) {
  if (item.kind === 'assignment_grading') {
    const studentId = item.student_id
    const assignmentId = item.assignment_id
    return {
      href: staffHref({ tab: 'pending', student_id: studentId, assignment_id: assignmentId }, 'instruction'),
      hintFa: 'پنل مدرس — ثبت تکلیف و پیگیری دانشجو',
    }
  }

  const instanceId = item.instance_id
  const studentId = item.student_id
  const code = (item.responsible_role_code || '').toLowerCase()
  const processCode = (item.process_code || '').toLowerCase()
  const stateCode = (item.state_code || '').toLowerCase()
  const base = { instance_id: instanceId, student_id: studentId }

  if (SEMESTER_PREP_CODES.has(processCode)) {
    if (
      processCode === 'fall_semester_preparation' &&
      stateCode === 'calendar_entry' &&
      COURSE_COMMITTEE_PREP_ROLES.has(code)
    ) {
      return {
        href: workbenchHref(processCode),
        hintFa: 'تدوین تقویم آموزشی دو ترم (پاییز و زمستان)',
      }
    }
    if (
      processCode === 'winter_semester_preparation' &&
      stateCode === 'course_list_review' &&
      COURSE_COMMITTEE_PREP_ROLES.has(code)
    ) {
      return {
        href: workbenchHref(processCode),
        hintFa: 'بازبینی و ویرایش لیست دروس ترم زمستان',
      }
    }
    if (
      ['tuition_entry', 'license_check'].includes(stateCode) &&
      DEPUTY_PREP_ROLES.has(code)
    ) {
      return {
        href: workbenchHref(processCode),
        hintFa: 'مرحلهٔ آماده‌سازی — معاون آموزش',
      }
    }
    if (
      ['interviewer_assignment', 'interview_scheduling'].includes(stateCode) &&
      (code === 'staff' || code === 'internal_manager')
    ) {
      return {
        href: workbenchHref(processCode),
        hintFa: 'مصاحبه‌ها — مدیر داخلی',
      }
    }
    if (
      ['course_list_creation', 'course_list_review', 'course_finalization'].includes(stateCode) &&
      COURSE_COMMITTEE_PREP_ROLES.has(code)
    ) {
      return {
        href: workbenchHref(processCode),
        hintFa: 'مرحلهٔ آماده‌سازی — کمیته دروس',
      }
    }
    if (
      stateCode === 'marketing_campaign' &&
      (code === 'admissions_officer' || code === 'admission_officer' || code === 'staff' || code === 'internal_manager')
    ) {
      return {
        href: workbenchHref(processCode),
        hintFa: 'شروع کمپین بازاریابی پذیرش',
      }
    }
    if (SEMESTER_PREP_CODES.has(processCode) && stateCode && stateCode !== 'published') {
      if (isStudentLikeRole(code)) {
        return {
          href: '/panel/academic-calendar',
          hintFa: 'تقویم آموزشی — آماده‌سازی ترم توسط کادر اجرایی انجام می‌شود',
        }
      }
      return {
        href: workbenchHref(processCode),
        hintFa: 'ادامه مرحلهٔ آماده‌سازی ترم',
      }
    }
    if (SEMESTER_PREP_CODES.has(processCode)) {
      if (isStudentLikeRole(code)) {
        return {
          href: '/panel/academic-calendar',
          hintFa: 'تقویم آموزشی منتشرشده',
        }
      }
      return {
        href: workbenchHref(processCode),
        hintFa: 'میز کار آماده‌سازی ترم',
      }
    }
  }

  if (isStudentLikeRole(code)) {
    return {
      href: studentPortalProcessesHref({
        ...base,
        process_code: processCode || undefined,
      }),
      hintFa: 'پنل آموزشی — فرایندهای من',
    }
  }

  const tracker = {
    href: `/panel/students${qs({ student_id: studentId, instance_id: instanceId, process_code: processCode || undefined })}`,
    hintFa: FALLBACK_HINT,
  }

  if (!instanceId || !studentId) {
    const processOnly = getOperatorFollowupDestinationForProcess({
      process_code: processCode,
      responsible_role_code: code,
      state_code: stateCode,
    })
    if (processOnly) return processOnly
    return tracker
  }

  if (processCode === 'introductory_term_end' && stateCode === 'followup_in_progress') {
    return {
      href: staffHref({ ...base, tab: 'pending' }, 'admissions'),
      hintFa: 'پنل پذیرش — پیگیری افت تحصیلی پایان ترم آشنایی',
    }
  }

  if (
    processCode === 'introductory_course_registration'
    && stateCode === 'documents_review'
  ) {
    return {
      href: staffHref({ ...base, tab: 'documentsReview' }, 'admissions'),
      hintFa: 'پنل پذیرش — بررسی مدارک ثبت‌نام',
    }
  }

  if (
    processCode === 'live_supervision_session_prep'
    || processCode === 'live_therapy_observation_session_prep'
  ) {
    if (stateCode === 'patient_referral' && (code === 'admission_officer' || code === 'admissions_officer')) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'admissions'),
        hintFa: 'پنل پذیرش — ارجاع بیمار برای جلسه زنده',
      }
    }
    if (stateCode === 'coordination_pending' && code === 'therapy_education_coordinator') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'therapy-coord'),
        hintFa: 'پنل هماهنگی درمان — تعیین زمان جلسه زنده',
      }
    }
  }

  if (processCode === 'intern_bulk_patient_referral') {
    if (stateCode === 'coordination_followup' && code === 'therapy_education_coordinator') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'therapy-coord'),
        hintFa: 'پنل هماهنگی درمان — پیگیری ارجاع بیماران',
      }
    }
    if (stateCode === 'supervision_start' && code === 'supervision_committee') {
      return {
        href: committeeHref({ ...base, tab: 'reviews' }, code),
        hintFa: 'پنل کمیته نظارت — ثبت جلسه و لیست بیماران',
      }
    }
    if (stateCode === 'general_therapy_committee_review' && code === 'therapy_committee_executor') {
      return {
        href: committeeHref({ ...base, tab: 'reviews' }, code),
        hintFa: 'پنل کمیته درمان — تکمیل ارجاع',
      }
    }
  }

  if (processCode === 'class_attendance') {
    if (stateCode === 'attendance_list_ready' || code === 'instructor') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — ثبت حضور و غیاب جلسه کلاس (فرایند ۵۴)',
      }
    }
  }

  if (processCode === 'article_writing_completion') {
    if (['course_active', 'instructor_eval_pending'].includes(stateCode)
      || code === 'instructor') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه درس مقاله‌نویسی (فرایند ۶۹)',
      }
    }
  }

  if (processCode === 'film_observation_ta_attendance_completion') {
    if (stateCode === 'grades_entry' || code === 'instructor') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه درس عملی کاربردی: مشارکت و حضور (فرایند ۷۵)',
      }
    }
  }

  if (processCode === 'film_observation_course_completion') {
    if (stateCode === 'grades_entry' || code === 'instructor') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه درس عملی کاربردی: گزارش PDF (فرایند ۶۴)',
      }
    }
  }

  if (processCode === 'skills_course_completion') {
    if (
      ['session_17_grades_entry', 'session_18_grades_entry', 'ta_evaluation_entry', 'qualitative_eval_pending'].includes(stateCode)
      || code === 'instructor'
    ) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه دروس تکنیک: تمرین مهارت‌ها (فرایند ۶۳)',
      }
    }
  }

  if (processCode === 'theory_course_completion') {
    if (
      ['session_18_entry', 'qualitative_eval_pending'].includes(stateCode)
      || code === 'instructor'
    ) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه دروس تئوری (فرایند ۶۱)',
      }
    }
  }

  if (processCode === 'group_supervision_course_completion') {
    if (
      ['session_18_pass_fail_entry', 'ta_evaluation_entry', 'qualitative_eval_pending'].includes(stateCode)
      || code === 'instructor'
    ) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه سوپرویژن گروهی (فرایند ۶۲)',
      }
    }
  }

  if (processCode === 'live_therapy_observation_course_completion') {
    if (stateCode === 'grades_entry' || code === 'instructor') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه درس مشاهده زنده درمان: گزارش PDF (فرایند ۶۵)',
      }
    }
  }

  if (processCode === 'live_supervision_course_completion') {
    if (
      ['sessions_in_progress', 'mirror_eval_pending', 'final_eval_pending'].includes(stateCode)
      || code === 'instructor'
    ) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — خاتمه درس سوپرویژن زنده (فرایند ۶۷)',
      }
    }
  }

  if (processCode === 'upgrade_to_ta') {
    if (stateCode === 'supervision_review' || code === 'supervision_committee') {
      return {
        href: committeeHref({ ...base, tab: 'reviews' }, 'supervision_committee'),
        hintFa: 'پنل کمیته نظارت — ارتقا به کمک‌مدرس (فرایند ۴۷)',
      }
    }
    if (
      ['interview_scheduling', 'interview_held', 'track_selection'].includes(stateCode)
      || ['course_committee', 'course_committee_scientific', 'course_committee_executive', 'scientific_officer_course_committee'].includes(code)
    ) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'course-committee'),
        hintFa: 'پنل کمیته دروس — مصاحبه/رسته ارتقا به کمک‌مدرس (فرایند ۴۷)',
      }
    }
  }

  if (processCode === 'thesis_defense_request') {
    if (stateCode === 'progress_committee_review' || code === 'progress_committee') {
      return {
        href: committeeHref({ ...base, tab: 'reviews' }, 'progress_committee'),
        hintFa: 'پنل کمیته پیشرفت — بررسی گزارش دفاع (فرایند ۷۰)',
      }
    }
    if (stateCode === 'supervision_committee_review' || code === 'supervision_committee') {
      return {
        href: committeeHref({ ...base, tab: 'reviews' }, 'supervision_committee'),
        hintFa: 'پنل کمیته نظارت — مجوز دفاع (فرایند ۷۰)',
      }
    }
    if (
      ['education_committee_scheduling', 'revision_upload'].includes(stateCode)
      || code === 'education_committee'
    ) {
      return {
        href: committeeHref({ ...base, tab: 'reviews' }, 'education_committee'),
        hintFa: 'پنل کمیته آموزش — زمان‌بندی دفاع (فرایند ۷۰)',
      }
    }
  }

  if (processCode === 'ta_to_instructor_auto') {
    if (
      ['deputy_education', 'deputy_education_director'].includes(code)
      || code === 'education'
    ) {
      return {
        href: committeeHref({ ...base, tab: 'reviews' }, 'education'),
        hintFa: 'پنل معاونت آموزش — گزارش ارتقای خودکار کمک‌مدرس به مدرس (فرایند ۵۰)',
      }
    }
    return {
      href: staffHref({ ...base, tab: 'pending' }, 'course-committee'),
      hintFa: 'پنل کمیته دروس — گزارش ارتقای خودکار کمک‌مدرس به مدرس (فرایند ۵۰)',
    }
  }

  if (processCode === 'ta_essay_upload') {
    if (['reference_center_editing', 'marketing_publication'].includes(stateCode)
      || ['reference_center', 'marketing'].includes(code)) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'content-ops'),
        hintFa: 'پنل تولید محتوا — مرکز مرجع / مارکتینگ',
      }
    }
    if (['ta_upload', 'instructor_review', 'rejected_revision'].includes(stateCode)
      || ['teaching_assistant', 'instructor'].includes(code)) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — آپلود جستار / بررسی مدرس',
      }
    }
  }

  if (processCode === 'mentor_private_sessions') {
    if (['instructor_click', 'sessions_registered', 'process_complete'].includes(stateCode)
      || ['instructor', 'teaching_assistant'].includes(code)) {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'instruction'),
        hintFa: 'پنل مدرس — ثبت تاریخ ۲ جلسه تدریس خصوصی (فرایند ۴۸)',
      }
    }
    if (stateCode === 'deadline_missed' || code === 'course_committee_scientific') {
      return {
        href: staffHref({ ...base, tab: 'pending' }, 'course-committee'),
        hintFa: 'کمیته دروس — هشدار عدم ثبت جلسات تدریس خصوصی',
      }
    }
  }

  if (code === 'therapist') {
    return {
      href: `/panel/portal/therapist${qs({ ...base, tab: 'pending' })}`,
      hintFa: 'پنل درمانگر — درخواست‌های منتظر',
    }
  }
  if (code === 'supervisor') {
    return {
      href: `/panel/portal/supervisor${qs({ ...base, tab: 'reviews' })}`,
      hintFa: 'پنل سوپروایزر — بررسی‌ها',
    }
  }
  if (code === 'site_manager') {
    return {
      href: `/panel/portal/site-manager${qs({ ...base, tab: 'pending' })}`,
      hintFa: 'پنل مسئول سایت — پیگیری‌ها',
    }
  }

  const committeeRoles = new Set([
    'committee',
    'progress_committee',
    'progress_committee_project',
    'education_committee',
    'supervision_committee',
    'specialized_commission',
    'therapy_committee_chair',
    'therapy_committee_executor',
    'deputy_education',
    'deputy_education_director',
    'monitoring_committee_officer',
    'course_committee_executive',
    'scientific_officer_course_committee',
  ])
  if (committeeRoles.has(code)) {
    return {
      href: committeeHref({ ...base, tab: 'reviews' }, code),
      hintFa: 'پنل کمیته — بررسی‌ها',
    }
  }

  if (code === 'interviewer') {
    return {
      href: `/panel/portal/interviewer${qs({ ...base, tab: 'result' })}`,
      hintFa: 'پنل مصاحبه‌گر — ثبت نتیجهٔ مصاحبه',
    }
  }

  const staffLike = new Set([
    'staff',
    'finance',
    'admissions_officer',
    'admission_officer',
    'instructor',
    'teaching_assistant',
    'teaching_assistant_or_instructor',
    'therapy_education_coordinator',
    'course_committee',
    'course_committee_scientific',
  ])
  if (staffLike.has(code)) {
    const lane = staffLaneForAssignedRole(code)
    return {
      href: staffHref({ ...base, tab: 'pending' }, lane),
      hintFa: 'پنل کارمند — وظایف منتظر',
    }
  }

  return tracker
}

/**
 * مقصد پیش‌فرض برای فرایند بدون نمونهٔ مشخص — سایدبار و صفحهٔ process-nav.
 * @param {{ process_code: string, responsible_role_code?: string, state_code?: string, portal_role?: string }} opts
 * @returns {{ href: string, hintFa: string } | null}
 */
export function getOperatorFollowupDestinationForProcess(opts) {
  const processCode = (opts.process_code || '').toLowerCase()
  const code = (opts.responsible_role_code || '').toLowerCase()
  const stateCode = (opts.state_code || '').toLowerCase()
  const portalRole = (opts.portal_role || '').toLowerCase()
  const filter = { process_code: processCode }

  if (SEMESTER_PREP_CODES.has(processCode)) {
    if (portalRole === 'student' || isStudentLikeRole(code)) {
      return {
        href: '/panel/academic-calendar',
        hintFa: 'تقویم آموزشی — آماده‌سازی ترم توسط کادر اجرایی انجام می‌شود',
      }
    }
    return {
      href: workbenchHref(processCode),
      hintFa: 'میز کار آماده‌سازی ترم',
    }
  }

  if (processCode === 'introductory_term_end' && stateCode === 'followup_in_progress') {
    return {
      href: staffHref({ tab: 'pending', process_code: processCode }, 'admissions'),
      hintFa: 'پنل پذیرش — پیگیری افت تحصیلی پایان ترم آشنایی',
    }
  }

  if (
    processCode === 'introductory_course_registration'
    && stateCode === 'documents_review'
  ) {
    return {
      href: staffHref({ tab: 'documentsReview', process_code: processCode }, 'admissions'),
      hintFa: 'پنل پذیرش — بررسی مدارک ثبت‌نام',
    }
  }

  if (portalRole === 'student' || isStudentLikeRole(code)) {
    return {
      href: studentPortalProcessesHref(filter),
      hintFa: 'پنل آموزشی — فرایندهای من',
    }
  }

  if (code === 'therapist') {
    return {
      href: `/panel/portal/therapist${qs({ tab: 'pending', ...filter })}`,
      hintFa: 'پنل درمانگر — درخواست‌های منتظر',
    }
  }
  if (code === 'supervisor') {
    return {
      href: `/panel/portal/supervisor${qs({ tab: 'reviews', ...filter })}`,
      hintFa: 'پنل سوپروایزر — بررسی‌ها',
    }
  }
  if (code === 'site_manager') {
    return {
      href: `/panel/portal/site-manager${qs({ tab: 'pending', ...filter })}`,
      hintFa: 'پنل مسئول سایت — پیگیری‌ها',
    }
  }
  if (code === 'interviewer') {
    return {
      href: `/panel/portal/interviewer${qs({ tab: 'result', ...filter })}`,
      hintFa: 'پنل مصاحبه‌گر — ثبت نتیجهٔ مصاحبه',
    }
  }

  const committeeRoles = new Set([
    'committee',
    'progress_committee',
    'progress_committee_project',
    'education_committee',
    'supervision_committee',
    'specialized_commission',
    'therapy_committee_chair',
    'therapy_committee_executor',
    'deputy_education',
    'deputy_education_director',
    'monitoring_committee_officer',
    'course_committee_executive',
    'scientific_officer_course_committee',
  ])
  if (committeeRoles.has(code)) {
    return {
      href: committeeHref({ tab: 'reviews', ...filter }, code),
      hintFa: 'پنل کمیته — بررسی‌ها',
    }
  }

  const staffLike = new Set([
    'staff',
    'finance',
    'admissions_officer',
    'admission_officer',
    'instructor',
    'teaching_assistant',
    'teaching_assistant_or_instructor',
    'therapy_education_coordinator',
    'course_committee',
    'course_committee_scientific',
  ])
  if (staffLike.has(code)) {
    const lane = staffLaneForAssignedRole(code)
    return {
      href: staffHref({ tab: 'pending', ...filter }, lane),
      hintFa: 'پنل کارمند — وظایف منتظر',
    }
  }

  if (processCode) {
    return {
      href: `/panel/students${qs(filter)}`,
      hintFa: FALLBACK_HINT,
    }
  }
  return null
}
