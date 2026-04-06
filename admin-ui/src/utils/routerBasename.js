/**
 * پایهٔ React Router: روی سرور زیر /anistito؛ وقتی اپ از ریشهٔ همان پورت سرو می‌شود (FastAPI + localhost:3000/) خالی.
 * بدون اسلش انتهایی — مطابق قرارداد react-router.
 */
export function getRouterBasename() {
  if (typeof window === 'undefined') {
    const b = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
    return b && b !== '/' ? b : ''
  }
  const p = window.location.pathname
  if (p === '/anistito' || p.startsWith('/anistito/')) return '/anistito'
  return ''
}
