/** سوال چالش لاگین: «حاصل ۷ + ۴ چند می‌شود؟» — ارقام فارسی یا لاتین */

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

function faDigitToEn(ch: string): string {
  const i = FA_DIGITS.indexOf(ch)
  return i >= 0 ? String(i) : ch
}

export function normalizePersianDigits(s: string): string {
  return s.replace(/[۰-۹]/g, faDigitToEn)
}

export function answerFromMathQuestion(visibleText: string): string {
  const t = normalizePersianDigits(visibleText)
  const m = t.match(/(\d+)\s*\+\s*(\d+)/)
  if (!m) return '0'
  return String(Number(m[1]) + Number(m[2]))
}
