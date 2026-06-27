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
    <fieldset
      className={`shamsi-datetime-picker${compact ? ' shamsi-datetime-picker--compact' : ''}`}
    >
      <legend className="shamsi-datetime-picker__legend">
        {label}
      </legend>
      <div
        className={`shamsi-datetime-picker__grid${compact ? ' shamsi-datetime-picker__grid--compact' : ''}`}
      >
        <label className="shamsi-datetime-picker__field">
          سال شمسی
          <select
            id={`${idPrefix}-y`}
            className="psf-input"
            value={jy}
            disabled={disabled}
            onChange={(e) => setPart({ jy: parseInt(e.target.value, 10) })}
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
        <label className="shamsi-datetime-picker__field">
          ماه
          <select
            id={`${idPrefix}-m`}
            className="psf-input"
            value={jm}
            disabled={disabled}
            onChange={(e) => setPart({ jm: parseInt(e.target.value, 10) })}
          >
            {JALAALI_MONTHS_FA.map((name, i) => (
              <option key={i + 1} value={i + 1}>{`${i + 1}. ${name}`}</option>
            ))}
          </select>
        </label>
        <label className="shamsi-datetime-picker__field">
          روز
          <select
            id={`${idPrefix}-d`}
            className="psf-input"
            value={Math.min(jd, maxDay)}
            disabled={disabled}
            onChange={(e) => setPart({ jd: parseInt(e.target.value, 10) })}
          >
            {days.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
        <label className="shamsi-datetime-picker__field">
          ساعت
          <input
            id={`${idPrefix}-h`}
            type="number"
            min={0}
            max={23}
            className="psf-input"
            dir="ltr"
            value={hour}
            disabled={disabled}
            onChange={(e) => setPart({ hour: Math.min(23, Math.max(0, parseInt(e.target.value, 10) || 0)) })}
          />
        </label>
        <label className="shamsi-datetime-picker__field">
          دقیقه
          <input
            id={`${idPrefix}-min`}
            type="number"
            min={0}
            max={59}
            className="psf-input"
            dir="ltr"
            value={minute}
            disabled={disabled}
            onChange={(e) => setPart({ minute: Math.min(59, Math.max(0, parseInt(e.target.value, 10) || 0)) })}
          />
        </label>
      </div>
      {!compact ? (
        <p className="shamsi-datetime-picker__hint muted">
          زمان به‌وقت رسمی ایران (۳۰+۳) ثبت می‌شود.
        </p>
      ) : (
        <p className="shamsi-datetime-picker__hint shamsi-datetime-picker__hint--compact muted">
          ایران (۳۰+۳).
        </p>
      )}
    </fieldset>
  )
}
