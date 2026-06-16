/**
 * مقصد کلیک از «صندوق پیگیری اپراتور» برای مدیر اصلی —
 * مسیر نقش‌محور به تب مناسب + instance_id برای باز شدن خودکار کارت فرایند.
 */
import { committeeKindForAssignedRole, getCommitteeKindPath } from './portalCommitteeKinds'
import { getStaffLanePath, staffLaneForAssignedRole } from './portalStaffLanes'

const FALLBACK_HINT = 'ردیابی دانشجو (همه نقش‌ها)'

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

/** @typedef {{ kind: string, instance_id?: string, student_id?: string, assignment_id?: string, responsible_role_code?: string }} FollowupItem */

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
  const base = { instance_id: instanceId, student_id: studentId }

  const tracker = {
    href: `/panel/students${qs({ student_id: studentId, instance_id: instanceId })}`,
    hintFa: FALLBACK_HINT,
  }

  if (!instanceId || !studentId) return tracker

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
      href: staffHref({ ...base, tab: 'pending' }, 'admissions'),
      hintFa: 'پنل پذیرش — ثبت نتیجهٔ مصاحبه و ادامهٔ فرایند',
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
