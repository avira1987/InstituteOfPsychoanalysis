import { canonicalPortalRole, userHasRole } from './userRoles.js'

/** نقش‌هایی که می‌توانند وقت مصاحبه تعریف و ویرایش کنند (مدیر داخلی و مدیر سیستم). */
export function canManageInterviewSlots(roleOrUser) {
  if (roleOrUser && typeof roleOrUser === 'object') {
    return userHasRole(roleOrUser, 'staff') || userHasRole(roleOrUser, 'admin')
  }
  const role = canonicalPortalRole(roleOrUser) || roleOrUser
  return role === 'staff' || role === 'admin'
}

export const interviewSlotsManagePath = '/panel/portal/staff/admissions?tab=interviewSlots'
