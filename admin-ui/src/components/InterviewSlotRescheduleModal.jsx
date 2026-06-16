import React, { useEffect, useState } from 'react'
import { interviewSlotsApi } from '../services/api'
import ShamsiDateTimePicker, { addMinutesToShamsiParts } from './ShamsiDateTimePicker'
import {
  isValidJalaaliDate,
  shamsiDateTimeToUtcIso,
  utcIsoToShamsiTehran,
} from '../utils/shamsiDateTime'

/**
 * مودال تغییر زمان اسلات رزرو قطعی (پس از پرداخت).
 */
export default function InterviewSlotRescheduleModal({ slot, onClose, onSaved, showToast }) {
  const [startsParts, setStartsParts] = useState(null)
  const [endsParts, setEndsParts] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!slot) return
    const sp = utcIsoToShamsiTehran(slot.starts_at)
    const ep = utcIsoToShamsiTehran(slot.ends_at)
    if (sp) setStartsParts(sp)
    if (ep) setEndsParts(ep)
    else if (sp) setEndsParts(addMinutesToShamsiParts(sp, 60) || sp)
  }, [slot])

  if (!slot || !startsParts || !endsParts) return null

  const submit = async (e) => {
    e.preventDefault()
    const { jy: sy, jm: sm, jd: sd, hour: sh, minute: smin } = startsParts
    const { jy: ey, jm: em, jd: ed, hour: eh, minute: emin } = endsParts
    if (!isValidJalaaliDate(sy, sm, sd) || !isValidJalaaliDate(ey, em, ed)) {
      showToast?.('تاریخ شمسی نامعتبر است.', 'error')
      return
    }
    let startsIso
    let endsIso
    try {
      startsIso = shamsiDateTimeToUtcIso(sy, sm, sd, sh, smin)
      endsIso = shamsiDateTimeToUtcIso(ey, em, ed, eh, emin)
    } catch {
      showToast?.('تاریخ یا زمان نامعتبر است.', 'error')
      return
    }
    if (new Date(endsIso) <= new Date(startsIso)) {
      showToast?.('پایان باید بعد از شروع باشد.', 'error')
      return
    }
    setSaving(true)
    try {
      await interviewSlotsApi.reschedule(slot.id, { starts_at: startsIso, ends_at: endsIso })
      showToast?.(
        slot.mode === 'online'
          ? 'زمان جدید ثبت شد و پیامک اطلاع‌رسانی برای دانشجو ارسال شد.'
          : 'زمان جدید ثبت شد.'
      )
      onSaved?.()
      onClose?.()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'تغییر زمان ناموفق بود.', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="interview-reschedule-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1200,
        background: 'rgba(15, 23, 42, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{ width: 'min(100%, 28rem)', padding: '1.25rem' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="interview-reschedule-title" className="card-title" style={{ marginBottom: '0.75rem' }}>
          تغییر زمان مصاحبه
        </h3>
        <p className="muted" style={{ fontSize: '0.88rem', marginBottom: '1rem', lineHeight: 1.6 }}>
          پس از ثبت، ورود دانشجو به جلسهٔ آنلاین تا ۳۰ دقیقه قبل از زمان جدید (یا فعال‌سازی دستی) بسته می‌ماند.
          {slot.mode === 'online' ? ' برای مصاحبهٔ آنلاین پیامک اطلاع‌رسانی ارسال می‌شود.' : ''}
        </p>
        <form onSubmit={submit}>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.35rem' }}>شروع</label>
            <ShamsiDateTimePicker value={startsParts} onChange={setStartsParts} />
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.35rem' }}>پایان</label>
            <ShamsiDateTimePicker value={endsParts} onChange={setEndsParts} />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-outline" onClick={onClose} disabled={saving}>
              انصراف
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'در حال ثبت…' : 'ثبت زمان جدید'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
