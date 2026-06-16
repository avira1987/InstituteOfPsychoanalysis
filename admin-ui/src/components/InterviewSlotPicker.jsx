import React, { useState, useEffect } from 'react'
import { interviewSlotsApi, publicApi } from '../services/api'
import OnlineMeetingJoinCta, { formatMeetingTimeTehran } from './OnlineMeetingJoinCta'

function formatSlotTehran(iso) {
  return formatMeetingTimeTehran(iso)
}

/**
 * رزرو وقت مصاحبه از وقت‌های تعریف‌شده توسط پذیرش (پس از انتخاب، فرایند به مرحلهٔ بعد می‌رود).
 */
export default function InterviewSlotPicker({ courseType, instanceId, onBooked }) {
  const [slots, setSlots] = useState([])
  const [myBookings, setMyBookings] = useState([])
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [booking, setBooking] = useState(false)
  const [err, setErr] = useState('')
  const [deadlineMinutes, setDeadlineMinutes] = useState(10)

  const load = () => {
    setLoading(true)
    setErr('')
    interviewSlotsApi
      .available(courseType)
      .then((r) => setSlots(r.data?.slots || []))
      .catch(() => setErr('بارگذاری وقت‌ها ناموفق بود.'))
      .finally(() => setLoading(false))
  }

  const loadMyBookings = () => {
    interviewSlotsApi
      .myBookings(false)
      .then((r) => setMyBookings(r.data?.bookings || []))
      .catch(() => {})
  }

  useEffect(() => {
    load()
    loadMyBookings()
    publicApi.portalConfig().then((r) => {
      const m = r.data?.interview_booking_payment_deadline_minutes
      if (m != null) setDeadlineMinutes(Number(m) || 10)
    }).catch(() => {})
  }, [courseType])

  const book = async () => {
    if (!selected || !instanceId) return
    setBooking(true)
    setErr('')
    try {
      const fresh = await interviewSlotsApi.available(courseType)
      const freshSlots = fresh.data?.slots || []
      setSlots(freshSlots)
      if (!freshSlots.some((s) => s.id === selected)) {
        setErr('این زمان دیگر آزاد نیست. لطفاً زمان دیگری انتخاب کنید.')
        setSelected('')
        return
      }
      await interviewSlotsApi.book({ instance_id: instanceId, slot_id: selected })
      if (onBooked) await onBooked()
      setSelected('')
      load()
      loadMyBookings()
    } catch (e) {
      const d = e.response?.data?.detail
      setErr(typeof d === 'string' ? d : 'رزرو انجام نشد.')
    } finally {
      setBooking(false)
    }
  }

  if (loading) {
    return (
      <div className="card interview-slot-picker" style={{ marginBottom: '1.25rem', padding: '1rem' }}>
        <p className="interview-slot-picker-loading" style={{ margin: 0 }}>
          در حال بارگذاری زمان‌های مصاحبه…
        </p>
      </div>
    )
  }

  if (!slots.length) {
    return (
      <div
        className="card interview-slot-picker"
        style={{
          marginBottom: '1.25rem',
          padding: '1rem 1.25rem',
          border: '1px solid rgba(234, 179, 8, 0.45)',
          background: 'linear-gradient(135deg, rgba(254, 252, 232, 0.95) 0%, #fff 100%)',
        }}
      >
        <h3 className="card-title interview-slot-picker-title" style={{ marginBottom: '0.5rem' }}>
          انتخاب زمان مصاحبه
        </h3>
        <p className="interview-slot-picker-body" style={{ margin: 0, fontSize: '0.95rem', lineHeight: 1.7 }}>
          هنوز زمان خالی برای مصاحبه از طرف مصاحبه‌گر در سامانه ثبت نشده است؛ تا قبل از تعریف وقت، پیشروی در این مسیر ممکن نیست.
          بعداً همین صفحه را تازه کنید یا در صورت نیاز با پذیرش تماس بگیرید.
        </p>
      </div>
    )
  }

  return (
    <div
      className="card interview-slot-picker"
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.25rem',
        border: '1px solid rgba(59, 130, 246, 0.35)',
        background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.95) 0%, #fff 100%)',
      }}
    >
      <h3 className="card-title interview-slot-picker-title" style={{ marginBottom: '0.5rem' }}>
        انتخاب زمان مصاحبه
      </h3>
      <p className="interview-slot-picker-lead" style={{ marginBottom: '1rem', fontSize: '0.92rem', lineHeight: 1.65 }}>
        یک زمان انتخاب و رزرو را تأیید کنید؛ پس از آن{' '}
        <strong>{deadlineMinutes.toLocaleString('fa-IR')} دقیقه</strong> مهلت دارید تا هزینهٔ مصاحبه را در درگاه پرداخت کنید. اگر تا پایان این مهلت پرداخت قطعی نشود، وقت برای دیگران آزاد می‌شود و باید دوباره زمان انتخاب کنید. با پرداخت موفق، وقت تا تاریخ مصاحبه برای شما محفوظ می‌ماند.
      </p>
      {!!myBookings.length && (
        <div style={{ marginBottom: '1rem', padding: '0.6rem 0.8rem', borderRadius: '10px', background: 'rgba(59, 130, 246, 0.08)' }}>
          <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>رزرو فعال شما:</div>
          {myBookings.slice(0, 1).map((b) => (
            <div key={b.id} style={{ fontSize: '0.84rem', lineHeight: 1.6 }}>
              <div>{formatSlotTehran(b.starts_at)}</div>
              {b.mode === 'online' ? (
                <OnlineMeetingJoinCta
                  compact
                  mode="online"
                  meetingLink={b.meeting_link}
                  meetingLinkOpenAt={b.meeting_link_open_at}
                  meetingLinkIsVisible={b.meeting_link_is_visible}
                  startsAt={b.starts_at}
                  studentJoinOpen={!!b.student_join_open}
                  label="ورود به مصاحبه آنلاین"
                  preparing={!b.meeting_link && !b.booking_payment_deadline_at}
                  preparingText="لینک پس از پرداخت موفق در همین صفحه نمایش داده می‌شود."
                />
              ) : (
                <span>{b.location_fa || 'حضوری'}</span>
              )}
            </div>
          ))}
        </div>
      )}
      <div
        className="interview-slot-picker-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '0.5rem',
          marginBottom: '1rem',
          maxHeight: slots.length > 12 ? '360px' : 'none',
          overflowY: slots.length > 12 ? 'auto' : 'visible',
          padding: slots.length > 12 ? '0.15rem' : 0,
        }}
      >
        {slots.map((s) => {
          const isSelected = selected === s.id
          const modeLabel = s.mode === 'online' ? 'آنلاین' : 'حضوری'
          const extraParts = []
          if (s.label_fa) extraParts.push(s.label_fa)
          if (s.location_fa && s.mode !== 'online') extraParts.push(s.location_fa)
          const extra = extraParts.join(' — ')
          return (
            <label
              key={s.id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.45rem',
                padding: '0.5rem 0.6rem',
                borderRadius: '8px',
                border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border)',
                cursor: 'pointer',
                background: isSelected ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-card)',
                lineHeight: 1.45,
              }}
            >
              <input
                type="radio"
                name="interview-slot"
                checked={isSelected}
                onChange={() => setSelected(s.id)}
                style={{ flexShrink: 0, marginTop: '0.2rem' }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  className="interview-slot-picker-slot-main"
                  style={{ fontWeight: 600, fontSize: '0.86rem' }}
                >
                  {formatSlotTehran(s.starts_at)}
                </div>
                <div
                  className="interview-slot-picker-slot-meta"
                  style={{
                    fontSize: '0.76rem',
                    marginTop: '0.15rem',
                    color: 'var(--text-secondary, #6b7280)',
                  }}
                >
                  {modeLabel}
                  {extra ? ` — ${extra}` : ''}
                </div>
              </div>
            </label>
          )
        })}
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

/**
 * خلاصهٔ رزرو تأییدشده (پس از پرداخت) — لینک الوکام برای دانشجو.
 */
const ALOCOM_LINK_POLL_MAX = 24

const PAID_BOOKING_CARD_STYLE = {
  marginTop: '0.85rem',
  padding: '1rem 1.25rem',
  border: '1px solid #e2e8f0',
  borderInlineStart: '4px solid #16a34a',
  borderRadius: '10px',
  background: '#ffffff',
  boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)',
  color: '#1e293b',
  isolation: 'isolate',
}

export function InterviewPaidBookingSummary() {
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [alocomPollExhausted, setAlocomPollExhausted] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      setLoading(true)
      interviewSlotsApi
        .myBookings(false)
        .then((r) => {
          if (!cancelled) setBookings(r.data?.bookings || [])
        })
        .catch(() => {
          if (!cancelled) setBookings([])
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const b = bookings[0]
  const pastOpen = !b?.meeting_link_open_at || Date.now() >= new Date(b.meeting_link_open_at).getTime()
  const needsLinkPoll =
    bookings.length > 0
    && b.mode === 'online'
    && !b.meeting_link
    && !b.booking_payment_deadline_at
    && pastOpen

  useEffect(() => {
    if (!needsLinkPoll) {
      setAlocomPollExhausted(false)
      return undefined
    }
    let cancelled = false
    let attempts = 0
    const poll = () => {
      attempts += 1
      if (attempts > ALOCOM_LINK_POLL_MAX) {
        if (!cancelled) setAlocomPollExhausted(true)
        return
      }
      interviewSlotsApi
        .myBookings(false)
        .then((r) => {
          if (!cancelled) setBookings(r.data?.bookings || [])
        })
        .catch(() => {})
    }
    const timer = setInterval(poll, 5000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [needsLinkPoll])

  if (loading) {
    return (
      <div className="card interview-paid-booking" style={PAID_BOOKING_CARD_STYLE}>
        <p style={{ margin: 0, color: '#64748b' }}>در حال بارگذاری جزئیات مصاحبه…</p>
      </div>
    )
  }

  if (!bookings.length) return null

  return (
    <div
      className="card interview-paid-booking"
      data-testid="student-interview-paid-booking"
      style={PAID_BOOKING_CARD_STYLE}
    >
      <h3 className="card-title" style={{ marginBottom: '0.5rem', color: '#15803d' }}>جزئیات مصاحبهٔ شما</h3>
      <div style={{ fontSize: '0.9rem', lineHeight: 1.7, color: '#1e293b' }}>
        <div><strong>زمان:</strong> {formatSlotTehran(b.starts_at)}</div>
        <div><strong>نوع:</strong> {b.mode === 'online' ? 'آنلاین' : 'حضوری'}</div>
        {b.mode === 'online' ? (
          <OnlineMeetingJoinCta
            mode="online"
            meetingLink={b.meeting_link}
            meetingLinkOpenAt={b.meeting_link_open_at}
            meetingLinkIsVisible={b.meeting_link_is_visible}
            startsAt={b.starts_at}
            studentJoinOpen={!!b.student_join_open}
            label="ورود به جلسهٔ مصاحبه"
            preparing={!b.meeting_link && !b.booking_payment_deadline_at}
            preparingFailed={alocomPollExhausted}
          />
        ) : (
          <div style={{ marginTop: '0.35rem' }}><strong>محل:</strong> {b.location_fa || '—'}</div>
        )}
      </div>
    </div>
  )
}
