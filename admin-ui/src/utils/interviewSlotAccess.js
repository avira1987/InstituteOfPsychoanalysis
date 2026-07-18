/** نقش‌هایی که می‌توانند وقت مصاحبه تعریف و ویرایش کنند (پذیرش، مدیر داخلی، مسئول سایت، مدیر سیستم). */
export function canManageInterviewSlots(role) {
  return role === 'staff' || role === 'admin' || role === 'site_manager'
}

export const interviewSlotsManagePath = '/panel/portal/staff/admissions?tab=interviewSlots'
