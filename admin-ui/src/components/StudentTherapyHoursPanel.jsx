import React, { useCallback, useEffect, useState } from 'react'
import { therapyApi } from '../services/api'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

const ATTENDANCE_FA = {
  present: 'حاضر',
  absent_excused: 'غایب موجه',
  absent_unexcused: 'غایب غیرموجه',
}

const PAYMENT_FA = {
  pending: 'در انتظار پرداخت',
  paid: 'پرداخت‌شده',
  waived: 'معاف',
}

function fmtDate(iso) {
  if (!iso) return '—'
  return formatShamsiTehran(iso)
}

function ProgressBar({ value, max, tone = '#16a34a' }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div style={{ marginTop: '0.35rem' }}>
      <div
        style={{
          height: '10px',
          borderRadius: '999px',
          background: '#e2e8f0',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: tone,
            borderRadius: '999px',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
        {pct.toLocaleString('fa-IR')}٪ از حدنصاب ۲۵۰ ساعت
      </div>
    </div>
  )
}

/**
 * داشبورد پیشرفت ساعات درمان — فرایند ۶ (attendance_tracking) — نمای دانشجو.
 */
export default function StudentTherapyHoursPanel({
  therapyHoursProgressFa = null,
  active = true,
  compact = false,
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await therapyApi.myTherapyProgress()
      setData(res.data)
    } catch (e) {
      setData(null)
      setError(e.response?.data?.detail || 'بارگذاری پیشرفت ساعات درمان ممکن نشد.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (active) load()
  }, [active, load])

  if (!active && !data) return null

  if (loading && !data) {
    return (
      <div className="card" data-testid="student-therapy-hours-panel">
        <div style={{ padding: '1.5rem', textAlign: 'center', fontSize: '0.9rem' }}>در حال بارگذاری…</div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="card" data-testid="student-therapy-hours-panel">
        <div className="card-header">
          <h3 className="card-title">پیشرفت ساعات درمان آموزشی</h3>
        </div>
        <div style={{ padding: '0 1rem 1rem', color: 'var(--danger)' }}>{error}</div>
      </div>
    )
  }

  const hours = Number(data?.therapy_hours_2x ?? 0)
  const goal = Number(data?.goal_hours ?? 250)
  const summary = data?.attendance_summary || {}
  const recent = (data?.recent_sessions || []).slice(0, compact ? 3 : 8)

  return (
    <div className="card" data-testid="student-therapy-hours-panel">
      <div className="card-header">
        <h3 className="card-title">پیشرفت ساعات درمان آموزشی (فرایند ۶)</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? '…' : 'بروزرسانی'}
        </button>
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        {therapyHoursProgressFa && (
          <p style={{ margin: '0 0 0.85rem', fontSize: '0.88rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            {therapyHoursProgressFa}
          </p>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          <div
            style={{
              padding: '0.85rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <div style={{ fontSize: '0.78rem', color: '#64748b' }}>ساعات ثبت‌شده</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#14532d' }}>
              {hours.toLocaleString('fa-IR')}
              <span style={{ fontSize: '0.85rem', fontWeight: 500 }}> / {goal.toLocaleString('fa-IR')}</span>
            </div>
            <ProgressBar value={hours} max={goal} />
          </div>

          {!compact && (
            <>
              <div style={{ padding: '0.85rem', borderRadius: '10px', background: '#eff6ff', borderRight: '4px solid #2563eb' }}>
                <div style={{ fontSize: '0.78rem', color: '#64748b' }}>جلسات در هفته</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#1d4ed8' }}>
                  {data?.weekly_sessions != null
                    ? Number(data.weekly_sessions).toLocaleString('fa-IR')
                    : '—'}
                </div>
              </div>
              <div style={{ padding: '0.85rem', borderRadius: '10px', background: '#f8fafc', borderRight: '4px solid #64748b' }}>
                <div style={{ fontSize: '0.78rem', color: '#64748b' }}>خلاصه حضور</div>
                <div style={{ fontSize: '0.85rem', lineHeight: 1.6, marginTop: '0.25rem' }}>
                  حاضر: {(summary.present ?? 0).toLocaleString('fa-IR')}
                  {' · '}
                  غایب موجه: {(summary.absent_excused ?? 0).toLocaleString('fa-IR')}
                  {' · '}
                  غایب: {(summary.absent_unexcused ?? 0).toLocaleString('fa-IR')}
                </div>
              </div>
            </>
          )}
        </div>

        {recent.length > 0 && (
          <>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem' }}>آخرین جلسات</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {recent.map((s) => (
                <div
                  key={s.session_id}
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    justifyContent: 'space-between',
                    gap: '0.35rem',
                    padding: '0.5rem 0.65rem',
                    borderRadius: '8px',
                    background: 'var(--bg)',
                    fontSize: '0.82rem',
                  }}
                >
                  <span>{fmtDate(s.session_date)}</span>
                  <span style={{ color: '#64748b' }}>
                    {PAYMENT_FA[s.payment_status] || s.payment_status}
                    {s.attendance_status && (
                      <>
                        {' · '}
                        <strong>{ATTENDANCE_FA[s.attendance_status] || s.attendance_status}</strong>
                      </>
                    )}
                    {!s.attendance_status && s.status === 'scheduled' && ' · در انتظار برگزاری'}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        <p style={{ margin: '0.85rem 0 0', fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6 }}>
          ثبت حضور توسط درمانگر آموزشی انجام می‌شود. هر جلسهٔ حاضر = ۱ ساعت به پیشرفت شما اضافه می‌شود.
        </p>
      </div>
    </div>
  )
}
