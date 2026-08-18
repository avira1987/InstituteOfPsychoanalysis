import { canonicalPortalRole } from './userRoles'

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
  const key = canonicalPortalRole(role) || role
  return key && REPORTS_HUB_ROLES.includes(key)
}
