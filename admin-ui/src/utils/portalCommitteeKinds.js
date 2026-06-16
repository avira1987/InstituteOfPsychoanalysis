/** تعریف kindهای پنل کمیته — مسیر، نقش‌های ورود، roleConfig */

export const COMMITTEE_KIND_IDS = ['progress', 'education', 'supervision', 'therapy']

/** @type {Record<string, { id: string, path: string, label: string, portalRoles: string[], showAllTab: boolean, priority: number }>} */
export const COMMITTEE_KINDS = {
  progress: {
    id: 'progress',
    path: '/panel/portal/committee/progress',
    label: 'کمیته پیشرفت',
    portalRoles: ['progress_committee'],
    showAllTab: true,
    priority: 25,
  },
  education: {
    id: 'education',
    path: '/panel/portal/committee/education',
    label: 'کمیته آموزش',
    portalRoles: ['education_committee', 'deputy_education'],
    showAllTab: false,
    priority: 25.1,
  },
  supervision: {
    id: 'supervision',
    path: '/panel/portal/committee/supervision',
    label: 'کمیته نظارت',
    portalRoles: ['supervision_committee', 'monitoring_committee_officer', 'specialized_commission'],
    showAllTab: false,
    priority: 25.2,
  },
  therapy: {
    id: 'therapy',
    path: '/panel/portal/committee/therapy',
    label: 'کمیته درمان',
    portalRoles: ['therapy_committee_chair', 'therapy_committee_executor'],
    showAllTab: false,
    priority: 25.3,
  },
}

/** roleConfig از CommitteePortal — به ازای User.role */
export const COMMITTEE_ROLE_CONFIG = {
  progress_committee: {
    title: 'پنل کمیته پیشرفت',
    subtitle: 'بررسی مرخصی‌ها، تغییرات درمان و پیشرفت دانشجویان',
    icon: '📈',
    accentColor: 'var(--success)',
    reviewKeywords: [
      'committee_review', 'progress_committee', 'leave_review', 'progress_review', 'awaiting_committee',
      'restart_review', 'therapist_change_review', 'interview_completed',
    ],
    assignedRoles: ['progress_committee', 'progress_committee_project', 'progress_committee_scientific'],
  },
  education_committee: {
    title: 'پنل کمیته آموزش',
    subtitle: 'بررسی نهایی و صدور حکم ادامه یا توقف',
    icon: '🎓',
    accentColor: 'var(--primary)',
    reviewKeywords: ['education_committee', 'education_review', 'final_verdict', 'continuation_review'],
    assignedRoles: ['education_committee'],
  },
  supervision_committee: {
    title: 'پنل کمیته نظارت',
    subtitle: 'بررسی موارد انضباطی و ارائه توصیه‌ها',
    icon: '🔍',
    accentColor: 'var(--warning)',
    reviewKeywords: ['supervision_committee', 'supervision_review', 'disciplinary_review'],
    assignedRoles: ['supervision_committee'],
  },
  specialized_commission: {
    title: 'پنل کمیسیون تخصصی',
    subtitle: 'بررسی قطع زودرس درمان و تصمیم‌گیری صلاحیت',
    icon: '⚖️',
    accentColor: 'var(--danger)',
    reviewKeywords: ['specialized_commission', 'commission_review', 'eligibility_review', 'early_termination'],
    assignedRoles: ['specialized_commission'],
  },
  therapy_committee_chair: {
    title: 'پنل مسئول کمیته درمان آموزشی',
    subtitle: 'واگذاری پیگیری و مشاهده موارد عدم حضور',
    icon: '🏥',
    accentColor: 'var(--info)',
    reviewKeywords: ['therapy_committee', 'chair_review', 'delegation', 'no_show'],
    assignedRoles: ['therapy_committee_chair'],
  },
  therapy_committee_executor: {
    title: 'پنل مجری کمیته درمان آموزشی',
    subtitle: 'پیگیری دانشجویان و ثبت گزارش',
    icon: '📝',
    accentColor: 'var(--primary)',
    reviewKeywords: ['executor_review', 'followup', 'executor_report', 'definitive_stop'],
    assignedRoles: ['therapy_committee_executor'],
  },
  deputy_education: {
    title: 'پنل معاون مدیر آموزش',
    subtitle: 'مشاهده هشدارهای SLA و درخواست‌های مرخصی',
    icon: '📊',
    accentColor: 'var(--warning)',
    reviewKeywords: ['deputy_review', 'sla_alert', 'escalation', 'deputy_education'],
    assignedRoles: ['deputy_education', 'deputy_education_director', 'scientific_officer_course_committee', 'course_committee_executive'],
  },
  monitoring_committee_officer: {
    title: 'پنل مسئول کمیته نظارت',
    subtitle: 'مشاهده هشدارهای تخلف و مدیریت ارجاع بیماران',
    icon: '🛡️',
    accentColor: 'var(--danger)',
    reviewKeywords: ['monitoring', 'violation', 'referral', 'monitoring_committee'],
    assignedRoles: ['monitoring_committee_officer'],
  },
}

export const COMMITTEE_DEFAULT_CONFIG = {
  title: 'پنل کمیته',
  subtitle: 'بررسی درخواست‌ها و تصمیم‌گیری',
  icon: '📋',
  accentColor: 'var(--primary)',
  reviewKeywords: ['review', 'committee', 'pending', 'awaiting'],
  assignedRoles: [],
}

const PORTAL_ROLE_TO_KIND = {}
for (const kindId of COMMITTEE_KIND_IDS) {
  for (const role of COMMITTEE_KINDS[kindId].portalRoles) {
    PORTAL_ROLE_TO_KIND[role] = kindId
  }
}

export function getCommitteeKindConfig(kindId) {
  return COMMITTEE_KINDS[kindId] || null
}

export function getCommitteeKindPath(kindId) {
  return COMMITTEE_KINDS[kindId]?.path || '/panel/portal/committee/progress'
}

export function committeeKindForPortalRole(portalRole) {
  return PORTAL_ROLE_TO_KIND[portalRole] || 'progress'
}

export function getCommitteeRoleConfig(portalRole) {
  return COMMITTEE_ROLE_CONFIG[portalRole] || COMMITTEE_DEFAULT_CONFIG
}

export function canAccessCommitteeKind(portalRole, kindId) {
  if (!portalRole || !kindId) return false
  if (portalRole === 'admin') return true
  const kind = COMMITTEE_KINDS[kindId]
  if (!kind) return false
  return kind.portalRoles.includes(portalRole)
}

export function committeeKindsForPortalRole(portalRole) {
  if (!portalRole) return []
  if (portalRole === 'admin') return COMMITTEE_KIND_IDS.map((id) => COMMITTEE_KINDS[id])
  const kindId = PORTAL_ROLE_TO_KIND[portalRole]
  if (!kindId) return []
  return [COMMITTEE_KINDS[kindId]]
}

/** نگاشت assigned_role یا responsible_role_code → kind */
export function committeeKindForAssignedRole(roleCode) {
  const code = (roleCode || '').trim()
  if (!code) return 'progress'
  for (const kindId of COMMITTEE_KIND_IDS) {
    for (const portalRole of COMMITTEE_KINDS[kindId].portalRoles) {
      const cfg = COMMITTEE_ROLE_CONFIG[portalRole]
      if (cfg?.assignedRoles?.includes(code)) return kindId
    }
  }
  const committeeRoleMap = {
    committee: 'progress',
    progress_committee: 'progress',
    progress_committee_project: 'progress',
    education_committee: 'education',
    deputy_education: 'education',
    deputy_education_director: 'education',
    course_committee_executive: 'education',
    scientific_officer_course_committee: 'education',
    supervision_committee: 'supervision',
    monitoring_committee_officer: 'supervision',
    specialized_commission: 'supervision',
    therapy_committee_chair: 'therapy',
    therapy_committee_executor: 'therapy',
  }
  return committeeRoleMap[code] || 'progress'
}

export const COMMITTEE_DEEP_LINK_TABS = ['dashboard', 'reviews', 'all', 'students']
