/**
 * لینک‌های سایدبار فرایند — مسیر پایدار و resolve مقصد نهایی.
 */
import { labelProcess } from './processDisplay'
import {
  getOperatorFollowupDestination,
  getOperatorFollowupDestinationForProcess,
} from './operatorFollowupDeepLinks'

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
  return list
    .map((row) => {
      const processCode = (row.process_code || '').trim()
      if (!processCode) return null
      return {
        processCode,
        label: (row.label_fa || labelProcess(processCode)).trim(),
        path: row.path || processNavSidebarPath(processCode),
        pendingCount: Number(row.pending_count) || 0,
        primaryAssignedRole: row.primary_assigned_role || '',
        icon: '📋',
        priority: 46,
        isProcessNav: true,
      }
    })
    .filter(Boolean)
    .sort((a, b) => a.label.localeCompare(b.label, 'fa'))
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
