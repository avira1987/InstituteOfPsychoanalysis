import React, { useState, useEffect } from 'react'
import { interviewSlotsApi } from '../services/api'

function formatSlotTehran(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('fa-IR', {
      timeZone: 'Asia/Tehran',
      weekday: 'short',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

/**
 * رزرو وقت مصاحبه از اسلات‌های تعریف‌شده توسط پذیرش (پس از انتخاب، فرایند به مرحلهٔ بعد می‌رود).
 */
export default function InterviewSlotPicker({ courseType, instanceId, onBooked }) {
  const [slots, setSlots] = useState([])
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [booking, setBooking] = useState(false)
  const [err, setErr] = useState('')

  const load = () => {
    setLoading(true)
    setErr('')
    interviewSlotsApi
      .available(courseType)
      .then((r) => setSlots(r.data?.slots || []))
      .catch(() => setErr('بارگذاری اسلات‌ها ناموفق بود.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [courseType])

  const book = async () => {
    if (!selected || !instanceId) return
    setBooking(true)
    setErr('')
    try {
      await interviewSlotsApi.book({ instance_id: instanceId, slot_id: selected })
      if (onBooked) await onBooked()
      setSelected('')
      load()
    } catch (e) {
      const d = e.response?.data?.detail
      setErr(typeof d === 'string' ? d : 'رزرو انجام نشد.')
    } finally {
      setBooking(false)
    }
  }

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: '1.25rem', padding: '1rem' }}>
        <p className="muted" style={{ margin: 0 }}>در حال بارگذاری زمان‌های مصاحبه…</p>
      </div>
    )
  }

  if (!slots.length) {
    return (
      <div
        className="card"
        style={{
          marginBottom: '1.25rem',
          padding: '1rem 1.25rem',
          border: '1px solid rgba(234, 179, 8, 0.45)',
          background: 'linear-gradient(135deg, rgba(254, 252, 232, 0.95) 0%, #fff 100%)',
        }}
      >
        <h3 className="card-title" style={{ marginBottom: '0.5rem' }}>انتخاب زمان مصاحبه</h3>
        <p style={{ margin: 0, fontSize: '0.95rem', lineHeight: 1.7 }}>
          هنوز زمان خالی برای مصاحبه در سامانه ثبت نشده است. لطفاً بعداً دوباره مراجعه کنید یا با پذیرش تماس بگیرید.
        </p>
      </div>
    )
  }

  return (
    <div
      className="card"
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.25rem',
        border: '1px solid rgba(59, 130, 246, 0.35)',
        background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.95) 0%, #fff 100%)',
      }}
    >
      <h3 className="card-title" style={{ marginBottom: '0.5rem' }}>انتخاب زمان مصاحبه</h3>
      <p className="muted" style={{ marginBottom: '1rem', fontSize: '0.92rem', lineHeight: 1.65 }}>
        یکی از زمان‌های زیر را انتخاب کنید و رزرو را تأیید کنید. پس از رزرو، این زمان برای شما حفظ می‌شود تا پایان مصاحبه.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
        {slots.map((s) => (
          <label
            key={s.id}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.65rem',
              padding: '0.65rem 0.75rem',
              borderRadius: '10px',
              border: selected === s.id ? '2px solid var(--primary)' : '1px solid var(--border)',
              cursor: 'pointer',
              background: selected === s.id ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-card)',
            }}
          >
            <input
              type="radio"
              name="interview-slot"
              checked={selected === s.id}
              onChange={() => setSelected(s.id)}
            />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{formatSlotTehran(s.starts_at)}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                {s.mode === 'online' ? 'آنلاین' : 'حضوری'}
                {s.label_fa ? ` — ${s.label_fa}` : ''}
                {s.location_fa && s.mode !== 'online' ? ` — ${s.location_fa}` : ''}
              </div>
            </div>
          </label>
        ))}
      </div>
      {err && (
        <p style={{ color: 'var(--danger, #dc2626)', marginBottom: '0.75rem', fontSize: '0.9rem' }}>{err}</p>
      )}
      <button
        type="button"
        className="btn btn-primary"
        disabled={!selected || booking}
        onClick={book}
      >
        {booking ? 'در حال رزرو…' : 'تأیید رزرو وقت مصاحبه'}
      </button>
    </div>
  )
}
