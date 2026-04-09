/**
 * دسترسی به بخش گزارشات — بر اساس نقش.
 * مدیر داخلی (کارمند دفتر) و مدیر سیستم اولویت کامل؛ سایر نقش‌ها برای تفکیک بعدی.
 */
const REPORTS_HUB_ROLES = [
  'admin',
  'staff',
  'deputy_education',
  'monitoring_committee_officer',
  'finance',
]

export function canAccessReportsHub(role) {
  return role && REPORTS_HUB_ROLES.includes(role)
}
