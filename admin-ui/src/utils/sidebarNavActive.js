/** نرمال‌سازی مسیر برای مقایسهٔ منوی کناری */
export function normalizeNavPath(path) {
  if (!path) return '/'
  const trimmed = String(path).replace(/\/+$/, '')
  return trimmed || '/'
}

/** آیا مسیر فعلی با آیتم منو هم‌خوان است؟ */
export function sidebarNavItemMatches(itemPath, pathname, { end = false } = {}) {
  const item = normalizeNavPath(itemPath)
  const current = normalizeNavPath(pathname)
  if (end) return current === item
  return current === item || current.startsWith(`${item}/`)
}

/**
 * طولانی‌ترین مسیر منو که با صفحهٔ فعلی جور است — فقط یک آیتم «انتخاب‌شده» می‌ماند.
 * داشبورد (/panel) فقط روی همان مسیر دقیق فعال می‌شود.
 */
export function resolveActiveSidebarNavPath(navItems, pathname) {
  const current = normalizeNavPath(pathname)
  if (current === '/panel') return '/panel'

  let best = null
  let bestLen = -1
  for (const item of navItems || []) {
    if (!item?.path) continue
    const itemPath = normalizeNavPath(item.path)
    const end = itemPath === '/panel' || itemPath === '/panel/portal/student'
    if (!sidebarNavItemMatches(item.path, pathname, { end })) continue
    if (itemPath.length > bestLen) {
      bestLen = itemPath.length
      best = itemPath
    }
  }
  return best
}
