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

export { isValidJalaaliDate, jalaaliMonthLength, toGregorian, toJalaali }

export const JALAALI_MONTHS_FA = [
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]
