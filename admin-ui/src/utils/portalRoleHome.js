/**
 * مسیر ورود پنل به ازای User.role — هم‌تراز با app/core/portal_role_home.py
 */
import { committeeKindForPortalRole, getCommitteeKindPath } from './portalCommitteeKinds'
import { getStaffLanePath } from './portalStaffLanes'

const STAFF_DEFAULT_LANE = 'admissions'

/** @type {Record<string, { path: string, tasksTab: string | null }>} */
export const PORTAL_ROLE_HOME = {
  student: { path: '/panel/portal/student', tasksTab: null },
  therapist: { path: '/panel/portal/therapist', tasksTab: 'pending' },
  supervisor: { path: '/panel/portal/supervisor', tasksTab: 'reviews' },
  staff: { path: getStaffLanePath(STAFF_DEFAULT_LANE), tasksTab: 'pending' },
  course_committee: { path: getStaffLanePath('course-committee'), tasksTab: 'pending' },
  teaching_assistant: { path: getStaffLanePath('instruction'), tasksTab: 'pending' },
  site_manager: { path: '/panel/portal/site-manager', tasksTab: 'pending' },
  interviewer: { path: '/panel/portal/interviewer', tasksTab: null },
  finance: { path: '/panel/finance', tasksTab: null },
  progress_committee: { path: getCommitteeKindPath('progress'), tasksTab: 'reviews' },
  education_committee: { path: getCommitteeKindPath('education'), tasksTab: 'reviews' },
  supervision_committee: { path: getCommitteeKindPath('supervision'), tasksTab: 'reviews' },
  specialized_commission: { path: getCommitteeKindPath('supervision'), tasksTab: 'reviews' },
  therapy_committee_chair: { path: getCommitteeKindPath('therapy'), tasksTab: 'reviews' },
  therapy_committee_executor: { path: getCommitteeKindPath('therapy'), tasksTab: 'reviews' },
  deputy_education: { path: getCommitteeKindPath('education'), tasksTab: 'reviews' },
  monitoring_committee_officer: { path: getCommitteeKindPath('supervision'), tasksTab: 'reviews' },
  admin: { path: '/panel', tasksTab: null },
}

const PORTAL_LABELS_FA = {
  student: 'پنل آموزشی',
  therapist: 'پنل درمانگر',
  supervisor: 'پنل سوپروایزر',
  staff: 'پنل پذیرش',
  course_committee: 'پنل کمیته دروس',
  teaching_assistant: 'پنل مدرس و کمک‌مدرس',
  site_manager: 'پنل مسئول سایت',
  interviewer: 'پنل مصاحبه‌گر',
  finance: 'داشبورد مالی',
  progress_committee: 'کمیته پیشرفت',
  education_committee: 'کمیته آموزش',
  supervision_committee: 'کمیته نظارت',
  specialized_commission: 'کمیته نظارت',
  therapy_committee_chair: 'کمیته درمان',
  therapy_committee_executor: 'کمیته درمان',
  deputy_education: 'کمیته آموزش',
  monitoring_committee_officer: 'کمیته نظارت',
}

const PORTAL_ICONS = {
  student: '🎓',
  therapist: '💊',
  supervisor: '👁️',
  staff: '🏢',
  course_committee: '📚',
  teaching_assistant: '🎓',
  site_manager: '🏗️',
  interviewer: '🎤',
}

/** @param {string | null | undefined} role */
export function getPortalHomePath(role) {
  const entry = role ? PORTAL_ROLE_HOME[role] : null
  return entry?.path ?? null
}

/** @param {string | null | undefined} role @returns {'pending' | 'reviews' | null} */
export function getPortalDefaultTasksTab(role) {
  const entry = role ? PORTAL_ROLE_HOME[role] : null
  return entry?.tasksTab ?? null
}

/** @param {string | null | undefined} role */
export function getPortalHomeHref(role) {
  const path = getPortalHomePath(role)
  if (!path) return '/panel'
  const tab = getPortalDefaultTasksTab(role)
  if (tab) {
    return `${path}?tab=${encodeURIComponent(tab)}`
  }
  return path
}

/** @param {string | null | undefined} role */
export function getPortalQuickLink(role) {
  const path = getPortalHomePath(role)
  if (!path || role === 'admin') return null
  return {
    path: getPortalHomeHref(role),
    label: PORTAL_LABELS_FA[role] || 'پنل نقش',
    icon: PORTAL_ICONS[role] || '📋',
  }
}

/** مسیر committee kind برای redirect از /panel/portal/committee */
export function getCommitteeHomePathForRole(role) {
  const kind = committeeKindForPortalRole(role)
  return getCommitteeKindPath(kind)
}

