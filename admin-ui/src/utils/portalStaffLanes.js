/** تعریف laneهای پنل کارمند — مسیر، تب‌ها، assigned_roleهای مرتبط */

export const STAFF_LANE_IDS = ['admissions', 'instruction', 'content-ops', 'therapy-coord', 'course-committee']

/** @type {Record<string, { id: string, path: string, label: string, title: string, subtitle: string, icon: string, tabIds: string[], assignedRoles: string[], allowedPortalRoles: string[], priority: number }>} */
export const STAFF_LANES = {
  admissions: {
    id: 'admissions',
    path: '/panel/portal/staff/admissions',
    label: 'پنل پذیرش',
    title: 'پنل پذیرش',
    subtitle: 'مدارک، مصاحبه و ثبت‌نام',
    icon: '📥',
    tabIds: ['pending', 'dashboard', 'documentsReview', 'interviewSlots', 'students'],
    assignedRoles: ['admissions_officer', 'admission_officer', 'interviewer'],
    allowedPortalRoles: ['admin', 'staff', 'interviewer'],
    priority: 23,
  },
  instruction: {
    id: 'instruction',
    path: '/panel/portal/staff/instruction',
    label: 'پنل مدرس',
    title: 'پنل مدرس و کمک‌مدرس',
    subtitle: 'کلاس، حضور و تکالیف',
    icon: '🎓',
    tabIds: ['pending', 'dashboard', 'students', 'onlineClasses'],
    assignedRoles: ['instructor', 'teaching_assistant', 'teaching_assistant_or_instructor'],
    allowedPortalRoles: ['admin', 'staff'],
    priority: 23.1,
  },
  'content-ops': {
    id: 'content-ops',
    path: '/panel/portal/staff/content-ops',
    label: 'تولید محتوا',
    title: 'پنل تولید محتوا',
    subtitle: 'مرکز مرجع و مارکتینگ',
    icon: '📝',
    tabIds: ['pending', 'dashboard'],
    assignedRoles: ['reference_center', 'marketing', 'admissions_officer'],
    allowedPortalRoles: ['admin', 'staff'],
    priority: 23.15,
  },
  'therapy-coord': {
    id: 'therapy-coord',
    path: '/panel/portal/staff/therapy-coord',
    label: 'هماهنگی درمان',
    title: 'پنل هماهنگی درمان آموزشی',
    subtitle: 'پیگیری و هماهنگی مراحل درمان',
    icon: '💊',
    tabIds: ['pending', 'dashboard', 'students', 'processes'],
    assignedRoles: ['therapy_education_coordinator'],
    allowedPortalRoles: ['admin', 'staff'],
    priority: 23.2,
  },
  'course-committee': {
    id: 'course-committee',
    path: '/panel/portal/staff/course-committee',
    label: 'کمیته دروس',
    title: 'پنل کمیته دروس (کارمند)',
    subtitle: 'بررسی علمی و اجرایی دروس',
    icon: '📚',
    tabIds: ['pending', 'dashboard', 'roster', 'processes', 'students'],
    assignedRoles: ['course_committee', 'course_committee_scientific', 'course_committee_executive', 'scientific_officer_course_committee'],
    allowedPortalRoles: ['admin', 'staff', 'course_committee'],
    priority: 23.3,
  },
}

const ALL_TAB_DEFS = {
  pending: { id: 'pending', labelKey: 'pending', icon: '📥' },
  dashboard: { id: 'dashboard', label: 'داشبورد', icon: '📊' },
  documentsReview: { id: 'documentsReview', labelKey: 'documentsReview', icon: '📎' },
  students: { id: 'students', label: 'دانشجویان', icon: '👨‍🎓' },
  processes: { id: 'processes', label: 'فرایندها', icon: '🔄' },
  roster: { id: 'roster', label: 'چارت مدرسین', icon: '👥' },
  interviewSlots: { id: 'interviewSlots', label: 'وقت مصاحبه', icon: '📅' },
  onlineClasses: { id: 'onlineClasses', label: 'کلاس آنلاین', icon: '🖥️' },
  activity: { id: 'activity', label: 'فعالیت‌ها', icon: '📝' },
}

export function getStaffLaneConfig(laneId) {
  return STAFF_LANES[laneId] || null
}

export function getStaffLanePath(laneId) {
  return STAFF_LANES[laneId]?.path || '/panel/portal/staff/admissions'
}

export function canAccessStaffLane(portalRole, laneId) {
  if (!portalRole || !laneId) return false
  if (portalRole === 'admin') return true
  const lane = STAFF_LANES[laneId]
  if (!lane) return false
  return lane.allowedPortalRoles.includes(portalRole)
}

export function staffLanesForPortalRole(portalRole) {
  if (!portalRole) return []
  if (portalRole === 'admin') return STAFF_LANE_IDS.map((id) => STAFF_LANES[id])
  return STAFF_LANE_IDS
    .map((id) => STAFF_LANES[id])
    .filter((lane) => lane.allowedPortalRoles.includes(portalRole))
}

export function buildStaffTabsForLane(laneId, counts = {}) {
  const lane = STAFF_LANES[laneId]
  if (!lane) return []
  return lane.tabIds.map((tabId) => {
    const def = ALL_TAB_DEFS[tabId]
    if (!def) return null
    let label = def.label
    if (tabId === 'pending') label = `کارهای من (${counts.pending ?? 0})`
    if (tabId === 'documentsReview') label = `بررسی مدارک (${counts.documentsReview ?? 0})`
    return { id: def.id, label, icon: def.icon }
  }).filter(Boolean)
}

export function laneAssignedRoles(laneId) {
  return STAFF_LANES[laneId]?.assignedRoles || []
}

/** تطبیق state فعلی با lane (heuristic — بدون assigned_role در لیست instance) */
export function stateMatchesStaffLane(state, laneId, processCode) {
  const s = (state || '').toLowerCase()
  if (!s) return false
  switch (laneId) {
    case 'admissions':
      if (
        processCode === 'live_supervision_session_prep'
        || processCode === 'live_therapy_observation_session_prep'
      ) {
        return s === 'patient_referral'
      }
      if (s === 'interview_completed') return true
      return (
        s.includes('staff') || s.includes('payment') || s.includes('office')
        || s.includes('document') || s.includes('admission') || s.includes('interview')
        || s.includes('registration')
      )
    case 'instruction':
      if (processCode === 'class_attendance' || processCode === 'lesson_start_per_term') return true
      if (processCode === 'class_session_cancellation') return true
      if (processCode === 'mentor_private_sessions') return true
      if (processCode === 'live_supervision_course_completion') return true
      if (processCode === 'film_observation_ta_attendance_completion') return true
      if (processCode === 'film_observation_course_completion') return true
      if (processCode === 'skills_course_completion') return true
      if (processCode === 'theory_course_completion') return true
      if (processCode === 'group_supervision_course_completion') return true
      if (processCode === 'ta_to_instructor_auto') return true
      if (processCode === 'article_writing_completion') {
        return ['course_active', 'instructor_eval_pending'].includes(s)
      }
      if (processCode && String(processCode).startsWith('ta_')) {
        if (processCode === 'ta_essay_upload') {
          return ['ta_upload', 'instructor_review', 'rejected_revision'].includes(s)
        }
        return true
      }
      return (
        s.includes('instructor') || s.includes('teaching') || s.includes('grade')
        || s.includes('attendance') || s.includes('assignment') || s.includes('ta_')
      )
    case 'content-ops':
      if (processCode === 'ta_essay_upload') {
        return ['reference_center_editing', 'marketing_publication'].includes(s)
      }
      return s.includes('reference_center') || s.includes('marketing_publication')
    case 'therapy-coord':
      if (processCode === 'intern_bulk_patient_referral' && s === 'coordination_followup') return true
      if (
        (processCode === 'live_supervision_session_prep'
          || processCode === 'live_therapy_observation_session_prep')
        && s === 'coordination_pending'
      ) {
        return true
      }
      return s.includes('therapy_education') || s.includes('therapy_coord') || s.includes('coordinator')
    case 'course-committee':
      if (processCode === 'ta_to_instructor_auto') return true
      if (processCode === 'ta_track_completion') return true
      if (processCode === 'class_session_cancellation') return true
      if (
        processCode === 'upgrade_to_ta'
        && ['interview_scheduling', 'interview_held', 'track_selection'].includes(s)
      ) {
        return true
      }
      if (processCode && (processCode.includes('semester') || processCode.includes('course'))) return true
      return s.includes('course_committee') || s.includes('course_list') || s.includes('calendar_entry')
    default:
      return false
  }
}

export function staffLaneForAssignedRole(roleCode) {
  const code = (roleCode || '').trim()
  if (!code) return 'admissions'
  if (code === 'admission_officer') return 'admissions'
  if (code === 'reference_center' || code === 'marketing') return 'content-ops'
  for (const id of STAFF_LANE_IDS) {
    if (STAFF_LANES[id].assignedRoles.includes(code)) return id
  }
  return 'admissions'
}
