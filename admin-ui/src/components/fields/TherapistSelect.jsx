import React, { useEffect, useState } from 'react'
import { studentApi } from '../../services/api'

export default function TherapistSelect({
  id,
  field,
  value,
  onChange,
  disabled,
  allowManualFallback = false,
}) {
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    studentApi
      .therapists()
      .then((res) => {
        if (!active) return
        setOptions(Array.isArray(res.data) ? res.data : [])
        setError(null)
      })
      .catch(() => {
        if (!active) return
        setOptions([])
        setError('دریافت فهرست درمانگران ممکن نشد؛ می‌توانید شناسه را دستی وارد کنید.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  if (allowManualFallback && error) {
    return (
      <>
        <p className="psf-hint psf-hint--warn">{error}</p>
        <input
          id={id}
          type="text"
          className="psf-input form-input"
          dir="ltr"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        />
      </>
    )
  }

  return (
    <select
      id={id}
      className="form-input psf-input"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || loading}
      data-testid="pf-therapist-select"
    >
      <option value="">{loading ? 'در حال بارگذاری…' : (field?.placeholder_fa || '— انتخاب کنید —')}</option>
      {options.map((opt) => (
        <option key={opt.id} value={opt.id}>{opt.label_fa}</option>
      ))}
    </select>
  )
}
