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
 * @param {{ label: string, value: ShamsiParts, onChange: (v: ShamsiParts) => void, idPrefix?: string, compact?: boolean }} props
 */
export default function ShamsiDateTimePicker({
  label,
  value,
  onChange,
  idPrefix = 'shamsi',
  compact = false,
  disabled = false,
}) {
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
      <legend
        style={{
          display: 'block',
          marginBottom: compact ? '0.2rem' : '0.35rem',
          fontSize: compact ? '0.82rem' : '0.88rem',
          fontWeight: 600,
        }}
      >
        {label}
      </legend>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: compact
            ? 'repeat(5, minmax(3.75rem, 1fr))'
            : 'repeat(auto-fill, minmax(7.5rem, 1fr))',
          gap: compact ? '0.3rem' : '0.5rem',
          alignItems: 'end',
        }}
      >
        <label style={{ fontSize: compact ? '0.72rem' : '0.8rem' }}>
          سال شمسی
          <select
            id={`${idPrefix}-y`}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            value={jy}
            disabled={disabled}
            onChange={(e) => setPart({ jy: parseInt(e.target.value, 10) })}
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: compact ? '0.72rem' : '0.8rem' }}>
          ماه
          <select
            id={`${idPrefix}-m`}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            value={jm}
            disabled={disabled}
            onChange={(e) => setPart({ jm: parseInt(e.target.value, 10) })}
          >
            {JALAALI_MONTHS_FA.map((name, i) => (
              <option key={i + 1} value={i + 1}>{`${i + 1}. ${name}`}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: compact ? '0.72rem' : '0.8rem' }}>
          روز
          <select
            id={`${idPrefix}-d`}
            className="psf-input"
            style={{ width: '100%', marginTop: '0.2rem' }}
            value={Math.min(jd, maxDay)}
            disabled={disabled}
            onChange={(e) => setPart({ jd: parseInt(e.target.value, 10) })}
          >
            {days.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: compact ? '0.72rem' : '0.8rem' }}>
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
            disabled={disabled}
            onChange={(e) => setPart({ hour: Math.min(23, Math.max(0, parseInt(e.target.value, 10) || 0)) })}
          />
        </label>
        <label style={{ fontSize: compact ? '0.72rem' : '0.8rem' }}>
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
            disabled={disabled}
            onChange={(e) => setPart({ minute: Math.min(59, Math.max(0, parseInt(e.target.value, 10) || 0)) })}
          />
        </label>
      </div>
      {!compact ? (
      <p className="muted" style={{ fontSize: '0.72rem', margin: '0.35rem 0 0' }}>
        زمان به‌وقت رسمی ایران (۳۰+۳) ثبت می‌شود.
      </p>
      ) : (
        <p className="muted" style={{ fontSize: '0.68rem', margin: '0.2rem 0 0', lineHeight: 1.35 }}>
          ایران (۳۰+۳).
        </p>
      )}
    </fieldset>
  )
}
