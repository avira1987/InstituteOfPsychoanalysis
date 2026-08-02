import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
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

function formatDateRange(start, end) {
  if (!start && !end) return '—'
  return `${formatDate(start)} تا ${formatDate(end)}`
}

function formatBreakPeriods(periods) {
  if (!Array.isArray(periods) || !periods.length) return null
  const parts = periods
    .filter((item) => item && (item.start || item.end))
    .map((item) => formatDateRange(item.start, item.end))
  return parts.length ? parts.join('؛ ') : null
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

function RegStatusBadge({ regStatus }) {
  if (!regStatus) return null
  return (
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
  )
}

function CalendarSection({ title, children }) {
  return (
    <section style={{ marginBottom: '1.1rem' }}>
      <h4
        style={{
          margin: '0 0 0.45rem',
          fontSize: '0.85rem',
          fontWeight: 700,
          color: '#334155',
        }}
      >
        {title}
      </h4>
      {children}
    </section>
  )
}

function CalendarDl({ rows }) {
  const visible = rows.filter((row) => row.value != null && row.value !== '—')
  if (!visible.length) return null
  return (
    <dl
      style={{
        margin: 0,
        display: 'grid',
        gridTemplateColumns: 'minmax(8rem, auto) 1fr',
        gap: '0.45rem 0.75rem',
        fontSize: '0.9rem',
      }}
    >
      {visible.map((row) => (
        <React.Fragment key={row.label}>
          <dt className="muted">{row.label}</dt>
          <dd style={{ margin: 0 }}>{row.value}</dd>
        </React.Fragment>
      ))}
    </dl>
  )
}

function CalendarBody({
  calendar,
  regStatus,
  variant,
  onOpenProcesses,
  showFullPageLink,
  showPrepDetailsLink,
}) {
  const extra = calendar.extra_data || {}
  const sourceProcessCode =
    calendar.source_process_code || extra.source_process_code || null
  const prepWorkbenchHref =
    sourceProcessCode === 'winter_semester_preparation' ||
    sourceProcessCode === 'fall_semester_preparation'
      ? `/panel/semester-prep/workbench?process_code=${sourceProcessCode}`
      : null
  const fallStart = extra.fall_start_date || (calendar.term_code?.startsWith('fall-') ? calendar.term_start_date : null)
  const fallEnd = extra.fall_end_date || (calendar.term_code?.startsWith('fall-') ? calendar.term_end_date : null)
  const winterStart = extra.winter_start_date || (calendar.term_code?.startsWith('winter-') ? calendar.term_start_date : null)
  const winterEnd = extra.winter_end_date || (calendar.term_code?.startsWith('winter-') ? calendar.term_end_date : null)
  const fallBreaks = formatBreakPeriods(extra.fall_break_periods)
  const winterBreaks = formatBreakPeriods(extra.winter_break_periods)
  const regRange =
    calendar.registration_open_at || calendar.registration_deadline_at
      ? `${formatDateTime(calendar.registration_open_at)} تا ${formatDateTime(calendar.registration_deadline_at)}`
      : formatDateRange(extra.registration_payment_window_start, extra.registration_payment_window_end)

  if (variant === 'compact') {
    return (
      <>
        <dl
          style={{
            margin: 0,
            display: 'grid',
            gridTemplateColumns: 'minmax(8rem, auto) 1fr',
            gap: '0.45rem 0.75rem',
            fontSize: '0.9rem',
          }}
        >
          <dt className="muted">ترم پاییز</dt>
          <dd style={{ margin: 0 }}>{formatDateRange(fallStart, fallEnd)}</dd>
          <dt className="muted">ترم زمستان</dt>
          <dd style={{ margin: 0 }}>{formatDateRange(winterStart, winterEnd)}</dd>
          <dt className="muted">ثبت‌نام و پرداخت</dt>
          <dd style={{ margin: 0 }}>
            {regRange}
            <RegStatusBadge regStatus={regStatus} />
          </dd>
        </dl>
        <div style={{ marginTop: '0.85rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          {showFullPageLink ? (
            <Link to="/panel/academic-calendar" className="btn btn-outline btn-sm">
              مشاهدهٔ کامل تقویم
            </Link>
          ) : null}
          {regStatus?.tone === 'open' && onOpenProcesses ? (
            <button type="button" className="btn btn-primary btn-sm" onClick={onOpenProcesses}>
              رفتن به ثبت‌نام / فرایندها
            </button>
          ) : null}
        </div>
      </>
    )
  }

  return (
    <>
      <CalendarSection title="ترم پاییز">
        <CalendarDl
          rows={[
            { label: 'شروع و پایان', value: formatDateRange(fallStart, fallEnd) },
            { label: 'دوره‌های تعطیلی', value: fallBreaks },
          ]}
        />
      </CalendarSection>

      <CalendarSection title="ترم زمستان">
        <CalendarDl
          rows={[
            { label: 'شروع و پایان', value: formatDateRange(winterStart, winterEnd) },
            { label: 'دوره‌های تعطیلی', value: winterBreaks },
          ]}
        />
      </CalendarSection>

      <CalendarSection title="ثبت‌نام، پرداخت و شهریه">
        <CalendarDl
          rows={[
            {
              label: 'پنجره ثبت‌نام',
              value: (
                <>
                  {regRange}
                  <RegStatusBadge regStatus={regStatus} />
                </>
              ),
            },
          ]}
        />
      </CalendarSection>

      <CalendarSection title="مهلت‌های مصاحبه">
        <CalendarDl
          rows={[
            {
              label: 'مصاحبه انترن‌ها',
              value: formatDateRange(
                extra.intern_interview_deadline_start,
                extra.intern_interview_deadline_end,
              ),
            },
            {
              label: 'مصاحبه کمک‌مدرس',
              value: formatDateRange(
                extra.teaching_assistant_interview_deadline_start,
                extra.teaching_assistant_interview_deadline_end,
              ),
            },
          ]}
        />
      </CalendarSection>

      <CalendarSection title="تعطیلات نوروز">
        <CalendarDl
          rows={[
            {
              label: 'بازه تعطیلات',
              value: formatDateRange(extra.nowruz_holiday_start, extra.nowruz_holiday_end),
            },
          ]}
        />
      </CalendarSection>

      <CalendarDl
        rows={[
          { label: 'ترم فعال', value: calendar.term_code || '—' },
          { label: 'تاریخ انتشار', value: calendar.published_at ? formatDateTime(calendar.published_at) : '—' },
        ]}
      />

      {regStatus?.tone === 'open' && onOpenProcesses ? (
        <div style={{ marginTop: '1rem' }}>
          <button type="button" className="btn btn-primary btn-sm" onClick={onOpenProcesses}>
            رفتن به ثبت‌نام / فرایندها
          </button>
        </div>
      ) : null}

      {showPrepDetailsLink && prepWorkbenchHref ? (
        <div
          style={{
            marginTop: '1rem',
            padding: '0.75rem 0.85rem',
            background: '#f0f9ff',
            borderRadius: '8px',
            border: '1px solid #bae6fd',
            lineHeight: 1.65,
          }}
          data-testid="academic-calendar-prep-details-link"
        >
          <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#334155' }}>
            برای مشاهدهٔ لیست دروس، برنامه نهایی و جزئیات آماده‌سازی ترم (فقط‌خواندنی):
          </p>
          <Link to={prepWorkbenchHref} className="btn btn-outline btn-sm">
            مشاهده جزئیات آماده‌سازی ترم
          </Link>
        </div>
      ) : null}
    </>
  )
}

/**
 * نمایش read-only تقویم آموزشی فعال انستیتو — پورتال دانشجو و صفحهٔ سراسری.
 * @param {'compact' | 'full'} variant
 */
export default function InstituteAcademicCalendarPanel({
  variant = 'full',
  onOpenProcesses,
  showFullPageLink = false,
  showPrepDetailsLink = false,
  testId = 'institute-academic-calendar-panel',
  embedded = true,
}) {
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

  const wrapperClass = embedded ? 'card' : ''
  const padding = embedded ? '0 1.25rem 1.25rem' : undefined

  if (loading) {
    return (
      <div className={wrapperClass} data-testid={testId}>
        {embedded ? (
          <div className="card-header">
            <h3 className="card-title">تقویم آموزشی</h3>
          </div>
        ) : null}
        <div style={{ padding }}>
          <p className="muted" style={{ margin: 0 }}>در حال بارگذاری…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={wrapperClass} data-testid={testId}>
        {embedded ? (
          <div className="card-header">
            <h3 className="card-title">تقویم آموزشی</h3>
          </div>
        ) : null}
        <div style={{ padding }}>
          <p style={{ margin: 0, color: '#b91c1c', fontSize: '0.9rem' }}>{error}</p>
        </div>
      </div>
    )
  }

  if (!calendar) {
    return (
      <div className={wrapperClass} data-testid={testId}>
        {embedded ? (
          <div className="card-header">
            <h3 className="card-title">تقویم آموزشی</h3>
          </div>
        ) : null}
        <div style={{ padding }}>
          <p className="muted" style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.65 }}>
            هنوز تقویم آموزشی رسمی برای ترم جاری منتشر نشده است. پس از آماده‌سازی ترم توسط انستیتو،
            تاریخ‌های مهم اینجا نمایش داده می‌شود.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={wrapperClass} data-testid={testId}>
      {embedded ? (
        <div className="card-header">
          <h3 className="card-title">تقویم آموزشی</h3>
          {calendar.term_code ? (
            <span className="badge badge-info" style={{ fontSize: '0.75rem' }}>
              {calendar.term_code}
            </span>
          ) : null}
        </div>
      ) : null}
      <div style={{ padding }}>
        <CalendarBody
          calendar={calendar}
          regStatus={regStatus}
          variant={variant}
          onOpenProcesses={onOpenProcesses}
          showFullPageLink={showFullPageLink}
          showPrepDetailsLink={showPrepDetailsLink}
        />
      </div>
    </div>
  )
}
