/** نقش‌هایی که می‌توانند وقت مصاحبه تعریف و ویرایش کنند (مسئول پذیر/مدیر داخلی + مدیر سیستم). */
export function canManageInterviewSlots(role) {
  return role === 'staff' || role === 'admin'
}

export const interviewSlotsManagePath = '/panel/portal/staff/admissions?tab=interviewSlots'
