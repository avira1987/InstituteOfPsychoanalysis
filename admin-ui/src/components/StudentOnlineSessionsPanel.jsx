import React, { useCallback, useEffect, useState } from 'react'
import { panelApi } from '../services/api'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

const KIND_BADGE = {
  therapy: { label: 'درمان', tone: '#1d4ed8' },
  interview: { label: 'مصاحبه', tone: '#7c3aed' },
  supervision: { label: 'سوپرویژن', tone: '#0d9488' },
  course: { label: 'کلاس', tone: '#b45309' },
}

function formatWhen(item) {
  const raw = item.starts_at || item.ends_at
  if (!raw) return 'بدون زمان مشخص'
  return formatShamsiTehran(raw)
}

function KindBadge({ kind }) {
  const meta = KIND_BADGE[kind] || { label: kind || '—', tone: '#6b7280' }
  return (
    <span
      className="badge"
      style={{
        fontSize: '0.7rem',
        background: `${meta.tone}14`,
        color: meta.tone,
        border: `1px solid ${meta.tone}33`,
      }}
    >
      {meta.label}
    </span>
  )
}

/**
 * لیست یکپارچهٔ جلسات و لینک‌های آنلاین دانشجو.
 */
export default function StudentOnlineSessionsPanel({
  studentProfile,
  active = true,
  onSessionsLoaded,
}) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!studentProfile) {
      setItems([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await panelApi.myOnlineSessions(false)
      const list = Array.isArray(res.data?.items) ? res.data.items : []
      setItems(list)
      onSessionsLoaded?.(list, res.data?.summary)
    } catch (e) {
      setItems([])
      setError(e.response?.data?.detail || 'بارگذاری جلسات آنلاین ممکن نشد.')
      onSessionsLoaded?.([], null)
    } finally {
      setLoading(false)
    }
  }, [studentProfile, onSessionsLoaded])

  useEffect(() => {
    if (active && studentProfile) {
      load()
    }
  }, [active, studentProfile, load])

  useEffect(() => {
    if (!active) return undefined
    const onFocus = () => {
      if (studentProfile) load()
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [active, studentProfile, load])

  if (!studentProfile) {
    return (
      <div className="card" data-testid="student-online-sessions-panel">
        <div className="card-header">
          <h3 className="card-title">جلسات آنلاین</h3>
        </div>
        <div className="empty-state" style={{ padding: '2rem' }}>پروفایل دانشجو یافت نشد.</div>
      </div>
    )
  }

  const withJoinLink = items.filter(
    (x) => x.meeting_link_is_visible && (x.meeting_link || '').trim(),
  ).length
  const awaitingLink = items.length > 0 && withJoinLink < items.length

  return (
    <div className="card" data-testid="student-online-sessions-panel">
      <div className="card-header" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 className="card-title" style={{ margin: 0 }}>جلسات آنلاین</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? 'در حال بارگذاری…' : 'تازه‌سازی'}
        </button>
      </div>

      {loading && items.length === 0 ? (
        <p style={{ padding: '1rem', color: 'var(--text-secondary)' }}>در حال بارگذاری جلسات…</p>
      ) : error ? (
        <p style={{ padding: '1rem', color: 'var(--danger, #b91c1c)' }}>{error}</p>
      ) : items.length === 0 ? (
        <p style={{ padding: '1rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          هنوز جلسه‌ای در تقویم شما ثبت نشده است. پس از تکمیل فرایند آغاز درمان، رزرو مصاحبه، یا ثبت‌نام کلاس،
          جلسات و لینک‌های ورود (اسکای‌روم / الوکام و …) در این بخش نمایش داده می‌شود.
        </p>
      ) : (
        <>
          {awaitingLink ? (
            <p style={{ padding: '0 1rem', margin: '0 0 0.5rem', fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              {items.length.toLocaleString('fa-IR')} جلسه/لینک ثبت شده است.
              {withJoinLink > 0
                ? ` ${withJoinLink.toLocaleString('fa-IR')} مورد آمادهٔ ورود است؛ بقیه پس از پرداخت و فعال‌سازی لینک توسط درمانگر/اپراتور نمایش داده می‌شود.`
                : ' لینک ورود پس از پرداخت موفق و فعال‌سازی توسط درمانگر یا اپراتور در همین بخش ظاهر می‌شود.'}
            </p>
          ) : null}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '0 1rem 1rem' }}>
            {items.map((item) => (
              <div
                key={`${item.kind}-${item.id}`}
                data-testid={`student-online-session-${item.kind}-${item.id}`}
                style={{
                  padding: '1rem',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  display: 'grid',
                  gap: '0.65rem',
                }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                    <KindBadge kind={item.kind} />
                    <span style={{ fontWeight: 600 }}>{item.title_fa}</span>
                  </div>
                  <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>{formatWhen(item)}</span>
                </div>
                {item.status_fa ? (
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{item.status_fa}</div>
                ) : null}
                <OnlineMeetingJoinCta
                  mode="online"
                  meetingLink={item.meeting_link}
                  meetingLinkOpenAt={item.meeting_link_open_at}
                  meetingLinkIsVisible={Boolean(item.meeting_link_is_visible)}
                  startsAt={item.starts_at}
                  studentJoinOpen={Boolean(item.student_join_open)}
                  label="ورود به جلسه"
                  compact
                  preparingText={
                    item.kind === 'therapy'
                      ? 'لینک جلسه پس از پرداخت و فعال‌سازی توسط درمانگر در همین بخش نمایش داده می‌شود.'
                      : 'لینک آنلاین در حال آماده‌سازی است؛ همین صفحه را کمی بعد تازه کنید.'
                  }
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
