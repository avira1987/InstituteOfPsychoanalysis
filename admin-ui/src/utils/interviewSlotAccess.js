import { canonicalPortalRole } from './userRoles'

/** نقش‌هایی که می‌توانند وقت مصاحبه تعریف و ویرایش کنند (مدیر داخلی و مدیر سیستم). */
export function canManageInterviewSlots(roleOrUser) {
  const role = typeof roleOrUser === 'string' || roleOrUser == null
    ? canonicalPortalRole(roleOrUser) || roleOrUser
    : canonicalPortalRole(roleOrUser.role) || roleOrUser.role
  return role === 'staff' || role === 'admin'
}

export const interviewSlotsManagePath = '/panel/portal/staff/admissions?tab=interviewSlots'
