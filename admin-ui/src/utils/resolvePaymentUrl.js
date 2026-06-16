/**
 * لینک بازگشتی ایجاد پرداخت: اگر API مقدار نسبی مثل `/payment/mock/...` بدهد،
 * بدون ترکیب با پیشوند اپ (Vite `BASE_URL`) مرورگر به `origin/payment/...` می‌رود
 * و خارج از SPA می‌افتد (اغلب به صفحهٔ اصلی سایت یا ۳۰۲ برمی‌گردد).
 * آدرس‌های مطلق `https://...` دست‌نخورده می‌مانند.
 */
export function resolvePaymentUrl(paymentUrl) {
  if (paymentUrl == null || paymentUrl === '') return paymentUrl
  const s = String(paymentUrl).trim()
  if (/^https?:\/\//i.test(s)) return s
  const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  const path = s.startsWith('/') ? s : `/${s}`
  if (typeof window === 'undefined') return path
  return `${window.location.origin}${base}${path}`
}
