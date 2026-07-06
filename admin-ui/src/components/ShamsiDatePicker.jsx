import React, { useMemo } from 'react'
import { jalaaliMonthLength, JALAALI_MONTHS_FA } from '../utils/shamsiDateTime'

/** @typedef {{ jy: number, jm: number, jd: number }} ShamsiDateParts */

/**
 * @param {{ label?: string, value: ShamsiDateParts, onChange: (v: ShamsiDateParts) => void, idPrefix?: string, compact?: boolean, disabled?: boolean }} props
 */
export default function ShamsiDatePicker({
  label,
  value,
  onChange,
  idPrefix = 'shamsi-date',
  compact = false,
  disabled = false,
}) {
  const { jy, jm, jd } = value
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

  const rootClass = `shamsi-datetime-picker shamsi-datetime-picker--date-only${compact ? ' shamsi-datetime-picker--compact' : ''}`
  const gridClass = `shamsi-datetime-picker__grid shamsi-datetime-picker__grid--date-only${compact ? ' shamsi-datetime-picker__grid--compact' : ''}`

  const grid = (
    <div className={gridClass}>
      <label className="shamsi-datetime-picker__field">
        سال شمسی
        <select
          id={`${idPrefix}-y`}
          className="psf-input form-input"
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
          className="psf-input form-input"
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
          className="psf-input form-input"
          value={Math.min(jd, maxDay)}
          disabled={disabled}
          onChange={(e) => setPart({ jd: parseInt(e.target.value, 10) })}
        >
          {days.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </label>
    </div>
  )

  if (!label) {
    return <div className={rootClass}>{grid}</div>
  }

  return (
    <fieldset className={rootClass}>
      <legend className="shamsi-datetime-picker__legend">
        {label}
      </legend>
      {grid}
    </fieldset>
  )
}
