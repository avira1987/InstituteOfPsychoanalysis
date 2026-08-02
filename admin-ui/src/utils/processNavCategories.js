/**
 * دسته‌بندی فرایندهای سایدبار — از پرکاربرد تا کم‌استفاده.
 * هم‌راستا با app/meta/process_nav_order.py (موج ۱، موج ۲، SOP، سایر).
 */
import { processNavUsageTier } from './processNavOrder'

/** @type {readonly { id: string, tier: number, label: string, hint: string }[]} */
export const PROCESS_NAV_CATEGORIES = [
  { id: 'core', tier: 0, label: 'فرایندهای اصلی', hint: 'پرکاربرد — چرخه آموزشی و عملیات روزمره' },
  { id: 'support', tier: 1, label: 'فرایندهای پشتیبانی', hint: 'مهم — کنار مسیر اصلی' },
  { id: 'sop', tier: 2, label: 'فرایندهای تکمیلی', hint: 'بر اساس ترتیب SOP' },
  { id: 'other', tier: 3, label: 'سایر فرایندها', hint: 'کم‌استفاده یا تخصصی' },
]

/**
 * @param {Array<{ processCode?: string, process_code?: string, label?: string, label_fa?: string, navTier?: number, nav_tier?: number, sop_order?: number | null }>} items
 */
export function resolveProcessNavTier(item) {
  const apiTier = item.navTier ?? item.nav_tier
  if (typeof apiTier === 'number' && apiTier >= 0 && apiTier <= 3) return apiTier
  return processNavUsageTier(
    item.processCode || item.process_code || '',
    item.label || item.label_fa || '',
    item.sop_order,
  )
}

/**
 * @param {Array<object>} items
 */
export function filterProcessNavItems(items, query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return items
  return items.filter((item) => {
    const label = (item.label || item.label_fa || '').toLowerCase()
    const code = (item.processCode || item.process_code || '').toLowerCase()
    return label.includes(q) || code.includes(q) || code.replace(/_/g, ' ').includes(q)
  })
}

/**
 * @param {Array<object>} items
 * @returns {Array<{ id: string, tier: number, label: string, hint: string, items: object[] }>}
 */
export function groupProcessNavItemsByCategory(items) {
  const buckets = Object.fromEntries(
    PROCESS_NAV_CATEGORIES.map((cat) => [cat.tier, { ...cat, items: [] }]),
  )
  for (const item of items) {
    const tier = resolveProcessNavTier(item)
    const bucket = buckets[tier] || buckets[3]
    bucket.items.push(item)
  }
  return PROCESS_NAV_CATEGORIES
    .map((cat) => buckets[cat.tier])
    .filter((group) => group.items.length > 0)
}

/**
 * @param {Array<object>} items
 * @param {string} [query]
 */
export function filterAndGroupProcessNavItems(items, query) {
  const filtered = filterProcessNavItems(items, query)
  return groupProcessNavItemsByCategory(filtered)
}

/**
 * @param {Array<{ id: string, tier: number, items: object[] }>} groups
 */
export function defaultProcessNavCategoryOpen(groups) {
  /** @type {Record<string, boolean>} */
  const state = {}
  for (const group of groups) {
    const hasPending = group.items.some((it) => Number(it.pendingCount || it.pending_count) > 0)
    state[group.id] = hasPending || group.tier <= 1
  }
  return state
}
