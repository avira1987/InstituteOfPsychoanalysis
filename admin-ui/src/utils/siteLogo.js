/**
 * فایل‌های استاتیک در admin-ui/public (بعد از build در ریشهٔ dist کپی می‌شوند):
 *   - logo.png        → لوگوی داخل صفحه (ترجیحاً بهینه‌شده؛ زیر ~۱۰۰KB)
 *   - favicon-32.png  → آیکن تب (۳۲×۳۲)
 *   - favicon-48.png  → آیکن / apple-touch-icon (۴۸×۴۸)
 * مسیر URL با توجه به آدرس واقعی (مثلاً /anistito/ پشت Apache یا پروکسی).
 */
function assetRootPath() {
  if (typeof window !== 'undefined') {
    const p = window.location.pathname || ''
    if (p === '/anistito' || p.startsWith('/anistito/')) {
      return '/anistito'
    }
  }
  const b = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  return b || ''
}

let _cachedLogoUrl = null

/** لوگوی داخل صفحه — PNG از public */
export function getSiteLogoUrl() {
  if (_cachedLogoUrl === null) {
    const root = assetRootPath()
    _cachedLogoUrl = root ? `${root}/logo.png` : '/logo.png'
  }
  return _cachedLogoUrl
}
