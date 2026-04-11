/** هم‌خوان با src/utils/persianDigits — برای assertionهای Playwright روی متن نمایش‌داده‌شده */
const FA = '۰۱۲۳۴۵۶۷۸۹'

export function toFaDigits(value: string | number | null | undefined): string {
  if (value == null) return ''
  return String(value).replace(/\d/g, (d) => FA[Number(d)] ?? d)
}
