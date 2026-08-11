/** دسته‌بندی سایدبار — هم‌راستا با ProcessNavSidebarSection */

export const SIDEBAR_NAV_GROUP_ORDER = [
  'home',
  'operations',
  'committees',
  'academic',
  'finance_reports',
  'admin_tools',
  'account',
]

/** @type {Record<string, { id: string, label: string, icon: string, defaultOpen: boolean, pinToFooter?: boolean }>} */
export const SIDEBAR_NAV_GROUPS = {
  home: {
    id: 'home',
    label: 'خانه',
    icon: '🏠',
    defaultOpen: true,
  },
  operations: {
    id: 'operations',
    label: 'عملیات روزانه',
    icon: '🛠️',
    defaultOpen: true,
  },
  committees: {
    id: 'committees',
    label: 'کمیته‌ها',
    icon: '📋',
    defaultOpen: false,
  },
  academic: {
    id: 'academic',
    label: 'آموزش و ترم',
    icon: '📆',
    defaultOpen: false,
  },
  finance_reports: {
    id: 'finance_reports',
    label: 'مالی و گزارش',
    icon: '📈',
    defaultOpen: false,
  },
  admin_tools: {
    id: 'admin_tools',
    label: 'ابزارهای فنی',
    icon: '⚙️',
    defaultOpen: false,
  },
  account: {
    id: 'account',
    label: 'حساب',
    icon: '👤',
    defaultOpen: false,
    pinToFooter: true,
  },
}

const PATH_GROUP_HINTS = [
  { test: (p) => p === '/panel' || p === '/panel/tickets' || p === '/panel/students', groupId: 'home' },
  { test: (p) => p.startsWith('/panel/portal/staff/'), groupId: 'operations' },
  { test: (p) => p.startsWith('/panel/portal/committee/'), groupId: 'committees' },
  {
    test: (p) =>
      p.startsWith('/panel/portal/') &&
      !p.startsWith('/panel/portal/staff/') &&
      !p.startsWith('/panel/portal/committee/') &&
      p !== '/panel/portal/student',
    groupId: 'operations',
  },
  { test: (p) => p === '/panel/portal/student', groupId: 'home' },
  {
    test: (p) =>
      p === '/panel/academic-calendar' ||
      p.startsWith('/panel/semester-prep') ||
      p === '/panel/automation-scheduler',
    groupId: 'academic',
  },
  {
    test: (p) =>
      p === '/panel/finance' || p === '/panel/reports' || p === '/panel/audit',
    groupId: 'finance_reports',
  },
  {
    test: (p) =>
      p === '/panel/users' ||
      p === '/panel/processes' ||
      p === '/panel/rules' ||
      p === '/panel/dynamic-forms' ||
      p === '/panel/system-resources' ||
      p === '/panel/backups',
    groupId: 'admin_tools',
  },
  { test: (p) => p === '/panel/profile' || p === '/panel/guide', groupId: 'account' },
]

export function inferSidebarGroupId(path) {
  const p = String(path || '')
  for (const hint of PATH_GROUP_HINTS) {
    if (hint.test(p)) return hint.groupId
  }
  return 'home'
}

export function resolveSidebarGroupId(item) {
  if (item?.groupId && SIDEBAR_NAV_GROUPS[item.groupId]) return item.groupId
  return inferSidebarGroupId(item?.path)
}

/**
 * @param {Array<object>} items
 * @returns {{ mainGroups: Array<{ id: string, label: string, icon: string, defaultOpen: boolean, items: object[] }>, footerItems: object[] }}
 */
export function groupSidebarNavItems(items) {
  const buckets = Object.fromEntries(SIDEBAR_NAV_GROUP_ORDER.map((id) => [id, []]))
  const unknown = []

  for (const item of items || []) {
    const groupId = resolveSidebarGroupId(item)
    if (buckets[groupId]) buckets[groupId].push(item)
    else unknown.push(item)
  }

  if (unknown.length) {
    buckets.home.push(...unknown)
  }

  const footerItems = buckets.account || []
  const mainGroups = SIDEBAR_NAV_GROUP_ORDER
    .filter((id) => id !== 'account')
    .map((id) => {
      const meta = SIDEBAR_NAV_GROUPS[id]
      const groupItems = buckets[id] || []
      return {
        id,
        label: meta.label,
        icon: meta.icon,
        defaultOpen: meta.defaultOpen,
        items: groupItems,
      }
    })
    .filter((g) => g.items.length > 0)

  return { mainGroups, footerItems }
}

export function defaultSidebarGroupOpen(groups) {
  const next = {}
  for (const g of groups || []) {
    next[g.id] = g.defaultOpen !== false
  }
  return next
}
