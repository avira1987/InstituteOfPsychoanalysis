import { STAFF_LANES, staffLanesForPortalRole } from './portalStaffLanes'
import { COMMITTEE_KINDS, committeeKindsForPortalRole } from './portalCommitteeKinds'

/** ابزارهای فنی — فقط admin (به‌جز automation-scheduler که staff/deputy هم می‌بینند) */
export const ADMIN_ONLY_PATHS = new Set([
  '/panel/processes',
  '/panel/rules',
  '/panel/dynamic-forms',
  '/panel/audit',
  '/panel/system-resources',
])

/** مسیرهای پورتال تک‌صفحه‌ای */
const SINGLE_PORTAL_NAV = [
  { path: '/panel/portal/student', label: 'پنل آموزشی', icon: '🎓', roles: ['student'], strictRoles: true, priority: 20 },
  { path: '/panel/portal/therapist', label: 'پنل درمانگر', icon: '💊', roles: ['therapist'], priority: 21 },
  { path: '/panel/portal/supervisor', label: 'پنل سوپروایزر', icon: '👁️', roles: ['supervisor'], priority: 22 },
  { path: '/panel/portal/interviewer', label: 'پنل مصاحبه‌گر', icon: '🎤', roles: ['interviewer', 'staff'], priority: 22 },
  { path: '/panel/portal/site-manager', label: 'پنل مسئول سایت', icon: '🏗️', roles: ['site_manager'], priority: 24 },
]

const SHARED_NAV = [
  { path: '/panel', label: 'داشبورد', icon: '📊', priority: 10 },
  {
    path: '/panel/tickets',
    label: 'تیکت‌ها و درخواست‌ها',
    icon: '🎫',
    roles: [
      'student', 'admin', 'staff', 'finance', 'therapist', 'supervisor', 'site_manager', 'interviewer',
      'progress_committee', 'education_committee', 'supervision_committee',
      'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor',
      'deputy_education', 'monitoring_committee_officer',
    ],
    priority: 35,
  },
  {
    path: '/panel/students',
    label: 'ردیابی دانشجو',
    icon: '👨‍🎓',
    roles: ['admin', 'staff', 'supervisor', 'therapist'],
    priority: 40,
  },
  {
    path: '/panel/reports',
    label: 'گزارشات',
    icon: '📈',
    roles: ['admin', 'staff', 'deputy_education', 'monitoring_committee_officer', 'finance'],
    priority: 42,
  },
  { path: '/panel/users', label: 'مدیریت کاربران', icon: '👥', roles: ['admin'], priority: 21.5 },
  {
    path: '/panel/academic-calendar',
    label: 'تقویم آموزشی',
    icon: '📆',
    roles: [
      'student', 'admin', 'staff', 'finance', 'therapist', 'supervisor', 'site_manager', 'interviewer',
      'deputy_education', 'course_committee', 'teaching_assistant', 'monitoring_committee_officer',
      'progress_committee', 'education_committee', 'supervision_committee', 'specialized_commission',
      'therapy_committee_chair', 'therapy_committee_executor', 'applicant', 'instructor',
      'admissions_officer',
    ],
    priority: 44,
  },
  /** workbench و هاب آماده‌سازی ترم از منوی «فرایندها» (process-nav) در دسترس‌اند؛ اینجا فقط ابزار مکمل SLA */
  {
    path: '/panel/semester-prep/sla-warnings',
    label: 'هشدارهای مهلت آماده‌سازی ترم',
    icon: '⏰',
    roles: ['admin', 'deputy_education', 'staff', 'course_committee'],
    priority: 45.25,
  },
  {
    path: '/panel/automation-scheduler',
    label: 'اتوماسیون زمان‌محور',
    icon: '⏱️',
    roles: ['admin', 'staff', 'deputy_education'],
    priority: 45.5,
  },
  { path: '/panel/finance', label: 'داشبورد مالی', icon: '💵', roles: ['admin', 'finance'], priority: 50 },
  { path: '/panel/profile', label: 'پروفایل من', icon: '👤', priority: 85 },
  { path: '/panel/guide', label: 'راهنمای جامع', icon: '📖', priority: 90 },
]

export const SCHEDULER_AUTOMATION_ROLES = ['admin', 'staff', 'deputy_education']

export function canViewSchedulerAutomation(portalRole) {
  return portalRole === 'admin' || SCHEDULER_AUTOMATION_ROLES.includes(portalRole)
}

function staffLaneNavItems(portalRole) {
  return staffLanesForPortalRole(portalRole).map((lane) => ({
    path: lane.path,
    label: lane.label,
    icon: lane.icon,
    roles: lane.allowedPortalRoles,
    priority: lane.priority,
  }))
}

function committeeKindNavItems(portalRole) {
  return committeeKindsForPortalRole(portalRole).map((kind) => ({
    path: kind.path,
    label: kind.label,
    icon: '📋',
    roles: kind.portalRoles,
    strictRoles: portalRole !== 'admin',
    priority: kind.priority,
  }))
}

/** آیتم‌های پایه منو — قبل از فیلتر نقش */
export function buildBaseNavItems() {
  const items = [...SHARED_NAV.filter((i) => !ADMIN_ONLY_PATHS.has(i.path))]
  for (const p of ADMIN_ONLY_PATHS) {
    const labels = {
      '/panel/processes': ['مدیریت فرایندها', '🔄', 47],
      '/panel/dynamic-forms': ['فرم‌های داینامیک', '📝', 46],
      '/panel/audit': ['گزارش حسابرسی', '📝', 46],
      '/panel/rules': ['مدیریت قوانین', '📋', 48],
      '/panel/system-resources': ['منابع سرور', '🖥️', 49],
    }
    const [label, icon, priority] = labels[p] || [p, '📋', 50]
    items.push({ path: p, label, icon, roles: ['admin'], priority })
  }
  items.push(...SINGLE_PORTAL_NAV)
  return items
}

export function buildPortalLaneNavItems(portalRole) {
  if (!portalRole) return []
  const staff = staffLaneNavItems(portalRole)
  const committee = committeeKindNavItems(portalRole)
  return [...staff, ...committee]
}

function itemVisibleForRole(item, portalRole) {
  if (!portalRole) return false
  if (ADMIN_ONLY_PATHS.has(item.path) && portalRole !== 'admin') return false
  if (portalRole === 'student' && item.path === '/panel') return false
  if (item.roles) {
    const inRole = item.roles.includes(portalRole)
    if (item.strictRoles) return inRole
    if (!inRole && portalRole !== 'admin') return false
  }
  return true
}

/** آیا این مسیر در منوی کناری برای نقش دیده می‌شود؟ */
export function isNavPathVisibleForRole(path, portalRole) {
  if (!path || !portalRole) return false
  if (portalRole === 'admin') return true
  if (ADMIN_ONLY_PATHS.has(path)) return false
  const all = [
    ...buildBaseNavItems(),
    ...buildPortalLaneNavItems(portalRole),
    ...Object.values(STAFF_LANES).map((l) => ({ path: l.path, roles: l.allowedPortalRoles })),
    ...Object.values(COMMITTEE_KINDS).map((k) => ({ path: k.path, roles: [...k.portalRoles, 'admin'] })),
  ]
  const item = all.find((i) => i.path === path)
  if (!item) {
    if (path.startsWith('/panel/process-nav/')) {
      return true
    }
    if (path.startsWith('/panel/portal/staff/')) {
      const laneId = path.replace('/panel/portal/staff/', '')
      return Object.values(STAFF_LANES).some((l) => l.id === laneId && l.allowedPortalRoles.includes(portalRole))
    }
    if (path.startsWith('/panel/portal/committee/')) {
      const kindId = path.replace('/panel/portal/committee/', '')
      const kind = COMMITTEE_KINDS[kindId]
      return kind && kind.portalRoles.includes(portalRole)
    }
    return false
  }
  return itemVisibleForRole(item, portalRole)
}

/** منوی کامل فیلترشده برای Layout */
export function navItemsForRole(portalRole) {
  const base = buildBaseNavItems().filter((item) => itemVisibleForRole(item, portalRole))
  const portals = buildPortalLaneNavItems(portalRole)
  const merged = [...base]
  for (const p of portals) {
    if (!merged.some((m) => m.path === p.path)) merged.push(p)
  }
  return merged.sort((a, b) => {
    const pa = a.priority ?? 50
    const pb = b.priority ?? 50
    if (pa !== pb) return pa - pb
    return a.path.localeCompare(b.path)
  })
}
