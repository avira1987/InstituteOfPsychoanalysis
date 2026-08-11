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
  const cadence = slot.week_interval_label_fa
    || (Number(slot.week_interval) === 2 ? 'هفته‌درمیان' : 'هفتگی')
  return `${slot.day_label_fa} ${slot.start_local_time}–${slot.end_local_time} (${cadence})`
}

/**
 * انتخاب درمانگر و اسلات‌ها از شیت وقت‌های آزاد کمیته نظارت.
 * خروجی: therapistId + slotIds[]
 */
export default function EducationalTherapistSlotPicker({
  therapistId = '',
  slotIds = [],
  weeklySessions = '',
  courseType = null,
  therapistFieldName = 'therapist_id',
  slotRole = 'therapist',
  onTherapistChange,
  onSlotsChange,
  disabled = false,
}) {
  const [therapists, setTherapists] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const isSupervisor = slotRole === 'supervisor'

  const weeklyRequired = useMemo(() => {
    const n = Number(weeklySessions)
    if (n > 0) return n
    if (isSupervisor) return 1
    if (courseType === 'comprehensive') return 2
    return 1
  }, [weeklySessions, courseType, isSupervisor])

  useEffect(() => {
    let active = true
    setLoading(true)
    setErr('')
    educationalTherapistSlotsApi
      .available(courseType || undefined, isSupervisor ? 'supervisor' : undefined)
      .then((r) => {
        if (!active) return
        setTherapists(r.data?.therapists || r.data?.supervisors || [])
      })
      .catch(() => {
        if (!active) return
        setErr(
          isSupervisor
            ? 'بارگذاری شیت وقت‌های آزاد سوپروایزرها ناموفق بود.'
            : 'بارگذاری شیت وقت‌های آزاد درمانگران ناموفق بود.',
        )
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [courseType, isSupervisor])

  const selectedTherapist = useMemo(
    () => therapists.find((t) => t.id === therapistId) || null,
    [therapists, therapistId],
  )

  const visibleSlotsForTherapist = (t) => {
    const slots = sortSlots(t.slots)
    if (courseType === 'comprehensive' && !isSupervisor) {
      return slots.filter((s) => Number(s.week_interval || 1) === 1)
    }
    return slots
  }

  const toggleSlot = (slotId, slotMeta) => {
    if (disabled) return
    if (courseType === 'comprehensive' && !isSupervisor && Number(slotMeta?.week_interval || 1) !== 1) {
      setErr('دوره جامع فقط وقت‌های هفتگی را می‌پذیرد.')
      return
    }
    const current = Array.isArray(slotIds) ? [...slotIds] : []
    const idx = current.indexOf(slotId)
    if (idx >= 0) {
      current.splice(idx, 1)
      onSlotsChange?.(current)
      return
    }
    if (current.length >= weeklyRequired) {
      setErr(`حداکثر ${weeklyRequired} اسلات می‌توانید انتخاب کنید.`)
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
          {isSupervisor
            ? 'در حال حاضر وقت آزاد سوپروایزر در شیت ثبت نشده است. لطفاً با هماهنگی انستیتو تماس بگیرید.'
            : 'در حال حاضر وقت آزاد درمانگر آموزشی در شیت ثبت نشده است. لطفاً با کمیته نظارت تماس بگیرید.'}
        </p>
      </div>
    )
  }

  return (
    <div className="et-slot-picker" data-testid="et-slot-picker">
      <p className="psf-hint" style={{ marginTop: 0 }}>
        {isSupervisor
          ? 'حداکثر ۱ جلسه در هفته با یک سوپروایزر انتخاب کنید.'
          : courseType === 'comprehensive'
            ? 'دوره جامع: دقیقاً ۲ جلسه هفتگی با یک درمانگر از شیت انتخاب کنید (بدون نیاز به تأیید مجدد درمانگر).'
            : 'دوره آشنایی: ۱ یا ۲ جلسه از شیت انتخاب کنید؛ پس از ثبت، مستقیم به زمان‌بندی و پرداخت می‌روید.'}
        {!isSupervisor && ' (فیلد «تعداد جلسات در هفته» را با تعداد اسلات هماهنگ کنید.)'}
      </p>
      {err && <p className="psf-hint psf-hint--warn">{err}</p>}

      <div className="et-slot-picker-therapists">
        {therapists.map((t) => {
          const active = t.id === therapistId
          const slots = visibleSlotsForTherapist(t)
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
                  {slots.length === 0 && (
                    <p className="psf-hint psf-hint--warn" style={{ margin: 0 }}>
                      برای دوره شما وقت هفتگی آزاد در این درمانگر نیست.
                    </p>
                  )}
                  {slots.map((slot) => {
                    const selected = (slotIds || []).includes(slot.id)
                    return (
                      <button
                        key={slot.id}
                        type="button"
                        className={`et-slot-chip${selected ? ' et-slot-chip--selected' : ''}`}
                        disabled={disabled}
                        onClick={() => toggleSlot(slot.id, slot)}
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
