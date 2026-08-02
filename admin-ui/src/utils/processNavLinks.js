/**
 * لینک‌های سایدبار فرایند — مسیر پایدار و resolve مقصد نهایی.
 */
import { labelProcess } from './processDisplay'
import {
  getOperatorFollowupDestination,
  getOperatorFollowupDestinationForProcess,
} from './operatorFollowupDeepLinks'
import { sortProcessNavItems } from './processNavOrder'
import { resolveProcessNavTier } from './processNavCategories'

export const PROCESS_NAV_PATH_PREFIX = '/panel/process-nav/'

export function processNavSidebarPath(processCode) {
  const code = (processCode || '').trim()
  return `${PROCESS_NAV_PATH_PREFIX}${encodeURIComponent(code)}`
}

/**
 * @param {Array<{ process_code: string, label_fa?: string, path?: string, pending_count?: number, primary_assigned_role?: string }>} items
 * @param {string} [portalRole]
 */
export function mapProcessNavItemsFromApi(items, portalRole = '') {
  const list = Array.isArray(items) ? items : []
  const mapped = list
    .map((row) => {
      const processCode = (row.process_code || '').trim()
      if (!processCode) return null
      const label = (row.label_fa || labelProcess(processCode)).trim()
      const item = {
        processCode,
        label,
        path: row.path || processNavSidebarPath(processCode),
        pendingCount: Number(row.pending_count) || 0,
        primaryAssignedRole: row.primary_assigned_role || '',
        navTier: typeof row.nav_tier === 'number' ? row.nav_tier : undefined,
        icon: '📋',
        priority: 46,
        isProcessNav: true,
      }
      if (item.navTier == null) {
        item.navTier = resolveProcessNavTier(item)
      }
      return item
    })
    .filter(Boolean)
  return sortProcessNavItems(mapped)
}

/**
 * @param {{
 *   processCode: string,
 *   portalRole?: string,
 *   primaryAssignedRole?: string,
 *   pendingItem?: object | null,
 * }} opts
 * @returns {{ href: string, hintFa: string }}
 */
export function resolveProcessLandingHref(opts) {
  const processCode = (opts.processCode || '').toLowerCase()
  const portalRole = (opts.portalRole || '').toLowerCase()
  const primaryRole = (opts.primaryAssignedRole || '').toLowerCase()
  const pending = opts.pendingItem

  if (pending && (pending.instance_id || pending.id)) {
    return getOperatorFollowupDestination({
      kind: 'process',
      instance_id: pending.instance_id || pending.id,
      student_id: pending.student_id,
      responsible_role_code: pending.responsible_role_code || primaryRole,
      process_code: pending.process_code || processCode,
      state_code: pending.state_code || pending.current_state || '',
    })
  }

  const roleCode = primaryRole || portalRole
  const dest = getOperatorFollowupDestinationForProcess({
    process_code: processCode,
    responsible_role_code: roleCode,
    portal_role: portalRole,
  })
  if (dest) return dest

  return {
    href: processNavSidebarPath(processCode),
    hintFa: labelProcess(processCode),
  }
}
