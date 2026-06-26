import React, { useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

function formatDate(value) {
  if (!value) return '—'
  return formatShamsiTehran(value, { dateOnly: true })
}

function formatDateTime(value) {
  if (!value) return '—'
  return formatShamsiTehran(value)
}

function registrationWindowStatus(openAt, deadlineAt) {
  if (!openAt && !deadlineAt) return null
  const now = Date.now()
  const openMs = openAt ? new Date(openAt).getTime() : null
  const endMs = deadlineAt ? new Date(deadlineAt).getTime() : null
  if (openMs != null && now < openMs) {
    return { label: 'هنوز باز نشده', tone: 'muted' }
  }
  if (endMs != null && now > endMs) {
    return { label: 'مهلت گذشته', tone: 'closed' }
  }
  return { label: 'مهلت باز است', tone: 'open' }
}

/**
 * نمایش read-only تقویم آموزشی فعال انستیتو در پورتال دانشجو (SOP گام ۹ آماده‌سازی ترم).
 */
export default function StudentAcademicCalendarPanel({ onOpenProcesses }) {
  const [loading, setLoading] = useState(true)
  const [calendar, setCalendar] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    panelApi
      .activeAcademicCalendar()
      .then((r) => {
        if (cancelled) return
        setCalendar(r.data || null)
        setError(null)
      })
      .catch(() => {
        if (cancelled) return
        setCalendar(null)
        setError('بارگذاری تقویم آموزشی ممکن نشد.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const regStatus = useMemo(
    () => registrationWindowStatus(calendar?.registration_open_at, calendar?.registration_deadline_at),
    [calendar],
  )

  if (loading) {
    return (
      <div className="card" data-testid="student-academic-calendar-panel">
        <div className="card-header">
          <h3 className="card-title">تقویم آموزشی</h3>
        </div>
        <div style={{ padding: '0 1.25rem 1.25rem' }}>
          <p className="muted" style={{ margin: 0 }}>در حال بارگذاری…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card" data-testid="student-academic-calendar-panel">
        <div className="card-header">
          <h3 className="card-title">تقویم آموزشی</h3>
        </div>
        <div style={{ padding: '0 1.25rem 1.25rem' }}>
          <p style={{ margin: 0, color: '#b91c1c', fontSize: '0.9rem' }}>{error}</p>
        </div>
      </div>
    )
  }

  if (!calendar) {
    return (
      <div className="card" data-testid="student-academic-calendar-panel">
        <div className="card-header">
          <h3 className="card-title">تقویم آموزشی</h3>
        </div>
        <div style={{ padding: '0 1.25rem 1.25rem' }}>
          <p className="muted" style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.65 }}>
            هنوز تقویم آموزشی رسمی برای ترم جاری منتشر نشده است. پس از آماده‌سازی ترم توسط انستیتو،
            تاریخ‌ها و مهلت ثبت‌نام اینجا نمایش داده می‌شود.
          </p>
        </div>
      </div>
    )
  }

  const extra = calendar.extra_data || {}

  return (
    <div className="card" data-testid="student-academic-calendar-panel">
      <div className="card-header">
        <h3 className="card-title">تقویم آموزشی</h3>
        {calendar.term_code ? (
          <span className="badge badge-info" style={{ fontSize: '0.75rem' }}>
            {calendar.term_code}
          </span>
        ) : null}
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <dl
          style={{
            margin: 0,
            display: 'grid',
            gridTemplateColumns: 'minmax(8rem, auto) 1fr',
            gap: '0.45rem 0.75rem',
            fontSize: '0.9rem',
          }}
        >
          <dt className="muted">شروع ترم</dt>
          <dd style={{ margin: 0 }}>{formatDate(calendar.term_start_date)}</dd>
          <dt className="muted">پایان ترم</dt>
          <dd style={{ margin: 0 }}>{formatDate(calendar.term_end_date)}</dd>
          <dt className="muted">ثبت‌نام و پرداخت</dt>
          <dd style={{ margin: 0 }}>
            {calendar.registration_open_at || calendar.registration_deadline_at
              ? `${formatDateTime(calendar.registration_open_at)} تا ${formatDateTime(calendar.registration_deadline_at)}`
              : '—'}
            {regStatus ? (
              <span
                style={{
                  display: 'inline-block',
                  marginRight: '0.5rem',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  color:
                    regStatus.tone === 'open'
                      ? '#15803d'
                      : regStatus.tone === 'closed'
                        ? '#b91c1c'
                        : '#64748b',
                }}
              >
                ({regStatus.label})
              </span>
            ) : null}
          </dd>
          {extra.nowruz_holiday_start || extra.nowruz_holiday_end ? (
            <>
              <dt className="muted">تعطیلات نوروز</dt>
              <dd style={{ margin: 0 }}>
                {formatDate(extra.nowruz_holiday_start)} تا {formatDate(extra.nowruz_holiday_end)}
              </dd>
            </>
          ) : null}
          {calendar.published_at ? (
            <>
              <dt className="muted">تاریخ انتشار</dt>
              <dd style={{ margin: 0 }}>{formatDateTime(calendar.published_at)}</dd>
            </>
          ) : null}
        </dl>

        {regStatus?.tone === 'open' && onOpenProcesses ? (
          <div style={{ marginTop: '1rem' }}>
            <button type="button" className="btn btn-primary btn-sm" onClick={onOpenProcesses}>
              رفتن به ثبت‌نام / فرایندها
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
