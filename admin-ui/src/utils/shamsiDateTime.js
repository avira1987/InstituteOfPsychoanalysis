import * as jalaali from 'jalaali-js'

const { isValidJalaaliDate, jalaaliMonthLength, toGregorian, toJalaali } = jalaali

function pad2(n) {
  return String(Math.max(0, n)).padStart(2, '0')
}

/**
 * زمان ورودی به‌عنوان ساعت رسمی ایران (IRST) روی تقویم میلادی معادل همان روز شمسی.
 * @returns {string} ISO UTC
 */
export function shamsiDateTimeToUtcIso(jy, jm, jd, hour, minute) {
  const { gy, gm, gd } = toGregorian(jy, jm, jd)
  const s = `${gy}-${pad2(gm)}-${pad2(gd)}T${pad2(hour)}:${pad2(minute)}:00+03:30`
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) throw new Error('Invalid date')
  return d.toISOString()
}

/**
 * از یک زمان UTC به تاریخ/ساعت تقویمی در منطقهٔ تهران و سپس به شمسی.
 * @returns {{ jy: number, jm: number, jd: number, hour: number, minute: number } | null}
 */
export function utcIsoToShamsiTehran(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const intl = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Tehran',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    hour12: false,
  })
  const parts = intl.formatToParts(d)
  const map = {}
  for (const p of parts) {
    if (p.type !== 'literal') map[p.type] = p.value
  }
  const gY = parseInt(map.year, 10)
  const gM = parseInt(map.month, 10)
  const gD = parseInt(map.day, 10)
  const hour = parseInt(map.hour, 10)
  const minute = parseInt(map.minute, 10)
  if ([gY, gM, gD, hour, minute].some((x) => Number.isNaN(x))) return null
  const { jy, jm, jd } = toJalaali(gY, gM, gD)
  return { jy, jm, jd, hour, minute }
}

export function defaultShamsiTehranNow() {
  return utcIsoToShamsiTehran(new Date().toISOString()) || { jy: 1403, jm: 1, jd: 1, hour: 9, minute: 0 }
}

/**
 * @param {string | null | undefined} isoDate YYYY-MM-DD
 * @returns {{ jy: number, jm: number, jd: number } | null}
 */
export function isoDateToShamsiParts(isoDate) {
  if (!isoDate) return null
  const s = String(isoDate).slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return null
  const gy = parseInt(m[1], 10)
  const gm = parseInt(m[2], 10)
  const gd = parseInt(m[3], 10)
  if ([gy, gm, gd].some((x) => Number.isNaN(x))) return null
  const { jy, jm, jd } = toJalaali(gy, gm, gd)
  return { jy, jm, jd }
}

/**
 * @returns {string} YYYY-MM-DD (Gregorian)
 */
export function shamsiDateToIsoDate(jy, jm, jd) {
  const { gy, gm, gd } = toGregorian(jy, jm, jd)
  return `${gy}-${pad2(gm)}-${pad2(gd)}`
}

/** @returns {{ jy: number, jm: number, jd: number }} */
export function defaultShamsiDate() {
  const now = utcIsoToShamsiTehran(new Date().toISOString())
  if (now) return { jy: now.jy, jm: now.jm, jd: now.jd }
  return { jy: 1403, jm: 1, jd: 1 }
}

/**
 * @param {string | null | undefined} iso ISO date or datetime
 * @param {{ dateOnly?: boolean, includeMonthName?: boolean }} [opts]
 * @returns {string}
 */
export function formatShamsiTehran(iso, opts = {}) {
  const { dateOnly = false, includeMonthName = true } = opts
  if (!iso) return '—'
  const p = dateOnly ? isoDateToShamsiParts(iso) : utcIsoToShamsiTehran(iso)
  if (!p) {
    try {
      return new Date(iso).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' })
    } catch {
      return String(iso)
    }
  }
  const mon = includeMonthName ? JALAALI_MONTHS_FA[p.jm - 1] || '' : ''
  const dateStr = `${p.jy}/${pad2(p.jm)}/${pad2(p.jd)}`
  if (dateOnly || p.hour == null) {
    return mon ? `${dateStr} (${mon})` : dateStr
  }
  const timeStr = `${pad2(p.hour)}:${pad2(p.minute)}`
  return mon ? `${dateStr} ${timeStr} (${mon})` : `${dateStr} ${timeStr}`
}

export { isValidJalaaliDate, jalaaliMonthLength, toGregorian, toJalaali }

export const JALAALI_MONTHS_FA = [
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]
