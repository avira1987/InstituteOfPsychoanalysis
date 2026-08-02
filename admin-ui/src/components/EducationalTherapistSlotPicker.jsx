import React, { useEffect, useMemo, useState } from 'react'
import { educationalTherapistSlotsApi } from '../services/api'

const DAY_ORDER = [5, 6, 0, 1, 2, 3, 4]

function sortSlots(slots) {
  return [...(slots || [])].sort((a, b) => {
    const da = DAY_ORDER.indexOf(a.day_of_week)
    const db = DAY_ORDER.indexOf(b.day_of_week)
    if (da !== db) return da - db
    return String(a.start_local_time).localeCompare(String(b.start_local_time))
  })
}

function slotLabel(slot) {
  return `${slot.day_label_fa} ${slot.start_local_time}–${slot.end_local_time}`
}

/**
 * انتخاب درمانگر و اسلات‌های هفتگی از شیت وقت‌های آزاد.
 * خروجی: therapistId + slotIds[]
 */
export default function EducationalTherapistSlotPicker({
  therapistId = '',
  slotIds = [],
  weeklySessions = '',
  courseType = null,
  therapistFieldName = 'therapist_id',
  onTherapistChange,
  onSlotsChange,
  disabled = false,
}) {
  const [therapists, setTherapists] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  const weeklyRequired = useMemo(() => {
    const n = Number(weeklySessions)
    if (n > 0) return n
    if (courseType === 'comprehensive') return 2
    return 1
  }, [weeklySessions, courseType])

  useEffect(() => {
    let active = true
    setLoading(true)
    setErr('')
    educationalTherapistSlotsApi
      .available(courseType || undefined)
      .then((r) => {
        if (!active) return
        setTherapists(r.data?.therapists || [])
      })
      .catch(() => {
        if (!active) return
        setErr('بارگذاری شیت وقت‌های آزاد درمانگران ناموفق بود.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [courseType])

  const selectedTherapist = useMemo(
    () => therapists.find((t) => t.id === therapistId) || null,
    [therapists, therapistId],
  )

  const toggleSlot = (slotId) => {
    if (disabled) return
    const current = Array.isArray(slotIds) ? [...slotIds] : []
    const idx = current.indexOf(slotId)
    if (idx >= 0) {
      current.splice(idx, 1)
      onSlotsChange?.(current)
      return
    }
    if (current.length >= weeklyRequired) {
      setErr(`حداکثر ${weeklyRequired} اسلات هفتگی می‌توانید انتخاب کنید.`)
      return
    }
    setErr('')
    onSlotsChange?.([...current, slotId])
  }

  const pickTherapist = (tid) => {
    if (disabled) return
    onTherapistChange?.(tid)
    onSlotsChange?.([])
    setErr('')
  }

  if (loading) {
    return (
      <div className="et-slot-picker" data-testid="et-slot-picker-loading">
        <p className="psf-hint" style={{ margin: 0 }}>در حال بارگذاری شیت وقت‌های آزاد…</p>
      </div>
    )
  }

  if (!therapists.length) {
    return (
      <div className="et-slot-picker" data-testid="et-slot-picker-empty">
        <p className="psf-hint psf-hint--warn" style={{ margin: 0 }}>
          در حال حاضر وقت آزاد درمانگر آموزشی در شیت ثبت نشده است. لطفاً با هماهنگی انستیتو تماس بگیرید.
        </p>
      </div>
    )
  }

  return (
    <div className="et-slot-picker" data-testid="et-slot-picker">
      <p className="psf-hint" style={{ marginTop: 0 }}>
        {courseType === 'comprehensive'
          ? 'دوره جامع: دقیقاً ۲ جلسه در هفته با یک درمانگر انتخاب کنید.'
          : 'دوره آشنایی: ۱ یا ۲ جلسه در هفته با یک درمانگر انتخاب کنید.'}
        {' '}
        (فیلد «تعداد جلسات در هفته» را با تعداد اسلات هماهنگ کنید.)
      </p>
      {err && <p className="psf-hint psf-hint--warn">{err}</p>}

      <div className="et-slot-picker-therapists">
        {therapists.map((t) => {
          const active = t.id === therapistId
          const slots = sortSlots(t.slots)
          return (
            <div
              key={t.id}
              className={`et-slot-picker-card${active ? ' et-slot-picker-card--active' : ''}`}
            >
              <button
                type="button"
                className="et-slot-picker-therapist-btn"
                disabled={disabled}
                onClick={() => pickTherapist(t.id)}
                data-testid={`et-therapist-${t.id}`}
              >
                <strong>{t.label_fa}</strong>
                <span className="et-slot-picker-meta">{slots.length} وقت آزاد</span>
              </button>
              {active && (
                <div className="et-slot-picker-slots">
                  {slots.map((slot) => {
                    const selected = (slotIds || []).includes(slot.id)
                    return (
                      <button
                        key={slot.id}
                        type="button"
                        className={`et-slot-chip${selected ? ' et-slot-chip--selected' : ''}`}
                        disabled={disabled}
                        onClick={() => toggleSlot(slot.id)}
                        data-testid={`et-slot-${slot.id}`}
                      >
                        {slotLabel(slot)}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {selectedTherapist && (slotIds || []).length > 0 && (
        <p className="psf-hint" style={{ marginBottom: 0 }}>
          انتخاب‌شده: {(slotIds || []).length} از {weeklyRequired} اسلات —
          {' '}
          {(slotIds || [])
            .map((id) => {
              const slot = (selectedTherapist.slots || []).find((s) => s.id === id)
              return slot ? slotLabel(slot) : id
            })
            .join('، ')}
        </p>
      )}
      <input type="hidden" name={therapistFieldName} value={therapistId || ''} readOnly />
    </div>
  )
}
