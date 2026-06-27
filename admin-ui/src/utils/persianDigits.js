const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'

/** ارقام فارسی/عربی → لاتین (ورود با کیبورد فارسی) */
export function toLatinDigits(value) {
  if (value == null) return ''
  return String(value)
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)))
}

/**
 * تبدیل ارقام لاتین (۰–۹ ASCII) به ارقام فارسی در یک رشته.
 * ارقام فارسی موجود بدون تغییر می‌مانند.
 */
export function toFaDigits(value) {
  if (value == null) return ''
  return String(value).replace(/\d/g, (d) => FA_DIGITS[Number(d)] ?? d)
}

/** عدد یا رشتهٔ عددی برای نمایش با locale فارسی (ارقام فارسی در مرورگرهای معمول). */
export function formatFaNumber(value, options) {
  if (value === null || value === undefined || value === '') return ''
  const n = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(n)) return toFaDigits(String(value))
  return new Intl.NumberFormat('fa-IR', options).format(n)
}
