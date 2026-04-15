import React, { useMemo } from 'react'
import {
  jalaaliMonthLength,
  JALAALI_MONTHS_FA,
  shamsiDateTimeToUtcIso,
  utcIsoToShamsiTehran,
} from '../utils/shamsiDateTime'

/** @typedef {{ jy: number, jm: number, jd: number, hour: number, minute: number }} ShamsiParts */

export function addMinutesToShamsiParts(parts, deltaMinutes) {
  const iso = shamsiDateTimeToUtcIso(parts.jy, parts.jm, parts.jd, parts.hour, parts.minute)
  const ms = new Date(iso).getTime() + deltaMinutes * 60 * 1000
  return utcIsoToShamsiTehran(new Date(ms).toISOString())
}

/**
 * @param {{ label: string, value: ShamsiParts, onChange: (v: ShamsiParts) => void, idPrefix?: string }} props
 */
export default function ShamsiDateTimePicker({ label, value, onChange, idPrefix = 'shamsi' }) {
  const { jy, jm, jd, hour, minute } = value
  const maxDay = useMemo(() => jalaaliMonthLength(jy, jm), [jy, jm])

  const setPart = (patch) => {
    const next = { ...value, ...patch }
    if (next.jd > jalaaliMonthLength(next.jy, next.jm)) {
      next.jd = jalaaliMonthLength(next.jy, next.jm)
    }
    onChange(next)
  }

  const years = useMemo(() => {
    const set = new Set()
    for (let y = 1398; y <= 1416; y += 1) set.add(y)
    set.add(jy)
    return [...set].sort((a, b) => a - b)
  }, [jy])

  const days = useMemo(() => {
    const n = jalaaliMonthLength(jy, jm)
    return Array.from({ length: n }, (_, i) => i + 1)
  }, [jy, jm])

  return (
    <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
      <legend style={{ display: 'block', marginBottom: '0.35rem', fontSize: '0.88rem', fontWeight: 600 }}>
        {label}
      </legend>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(7.5rem, 1fr))',
          gap: '0.5rem',
          alignItems: 'end',
        }}
      >
        <label style={{ fontSize: '0.8rem' }}>
          سال شمسی
          <select
            id={`${idPrefix}-y`}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            value={jy}
            onChange={(e) => setPart({ jy: parseInt(e.target.value, 10) })}
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: '0.8rem' }}>
          ماه
          <select
            id={`${idPrefix}-m`}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            value={jm}
            onChange={(e) => setPart({ jm: parseInt(e.target.value, 10) })}
          >
            {JALAALI_MONTHS_FA.map((name, i) => (
              <option key={i + 1} value={i + 1}>{`${i + 1}. ${name}`}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: '0.8rem' }}>
          روز
          <select
            id={`${idPrefix}-d`}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            value={Math.min(jd, maxDay)}
            onChange={(e) => setPart({ jd: parseInt(e.target.value, 10) })}
          >
            {days.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: '0.8rem' }}>
          ساعت
          <input
            id={`${idPrefix}-h`}
            type="number"
            min={0}
            max={23}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            dir="ltr"
            value={hour}
            onChange={(e) => setPart({ hour: Math.min(23, Math.max(0, parseInt(e.target.value, 10) || 0)) })}
          />
        </label>
        <label style={{ fontSize: '0.8rem' }}>
          دقیقه
          <input
            id={`${idPrefix}-min`}
            type="number"
            min={0}
            max={59}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            dir="ltr"
            value={minute}
            onChange={(e) => setPart({ minute: Math.min(59, Math.max(0, parseInt(e.target.value, 10) || 0)) })}
          />
        </label>
      </div>
      <p className="muted" style={{ fontSize: '0.72rem', margin: '0.35rem 0 0' }}>
        زمان به‌وقت رسمی ایران (۳۰+۳) ثبت می‌شود.
      </p>
    </fieldset>
  )
}
