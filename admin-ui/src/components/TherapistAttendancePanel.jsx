import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { therapyApi } from '../services/api'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { formatStudentCodeDisplay, labelState } from '../utils/processDisplay'

const PAYMENT_FA = {
  pending: 'پرداخت نشده',
  paid: 'پرداخت‌شده',
  waived: 'معاف',
}

const RECORDED_FA = {
  present: 'حاضر',
  absent_excused: 'غایب موجه',
  absent_unexcused: 'غایب غیرموجه',
}

const BLOCK_FA = {
  session_cancelled: 'جلسه کنسل شده',
  unpaid: 'پرداخت نشده — فقط غیبت قابل ثبت',
  already_recorded: 'قبلاً ثبت شده',
  recording_closed: 'ثبت بسته (وقفه/کنسلی)',
  auto_absence_unpaid: 'غیبت خودکار (پرداخت نشده)',
  session_completed: 'جلسه تکمیل شده',
  excused_absence: 'غیبت موجه ثبت شد',
  unexcused_absence: 'غیبت غیرموجه ثبت شد',
}

function fmtDate(iso) {
  if (!iso) return '—'
  return formatShamsiTehran(iso)
}

function StatTile({ label, value, tone = '#14532d', bg = '#f0fdf4' }) {
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: tone }}>{value}</div>
    </div>
  )
}

/**
 * میزکار فرایند ۶ — ثبت حضور و غیاب جلسات درمان آموزشی (attendance_tracking).
 */
export default function TherapistAttendancePanel({
  active = true,
  onRecorded,
  showToast,
  compact = false,
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [filter, setFilter] = useState('needs_recording')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await therapyApi.attendanceWorkbench()
      setData(res.data || { stats: {}, sessions: [] })
    } catch (e) {
      setData(null)
      setError(e.response?.data?.detail || 'بارگذاری میزکار حضور و غیاب ممکن نشد.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (active) load()
  }, [active, load])

  const sessions = data?.sessions || []
  const stats = data?.stats || {}

  const filtered = useMemo(() => {
    if (filter === 'all') return sessions
    if (filter === 'needs_recording') return sessions.filter((s) => s.can_record)
    if (filter === 'recorded') {
      return sessions.filter((s) => s.recorded_status || ['session_completed', 'excused_absence', 'unexcused_absence'].includes(s.attendance_process_state))
    }
    return sessions.filter((s) => {
      if (s.can_record) return false
      if (s.recorded_status) return false
      return Boolean(s.record_block_reason) && s.record_block_reason !== 'unpaid'
    })
  }, [sessions, filter])

  const record = async (sessionId, attendanceStatus) => {
    setBusyId(sessionId)
    try {
      await therapyApi.patchSession(sessionId, { attendance_status: attendanceStatus })
      showToast?.('حضور و غیاب ثبت شد')
      await load()
      onRecorded?.()
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : (e.message || 'خطا در ثبت'), 'error')
    } finally {
      setBusyId(null)
    }
  }

  if (loading && !data) {
    return (
      <div className="card" data-testid="therapist-attendance-panel">
        <div style={{ padding: '2rem', textAlign: 'center' }}>در حال بارگذاری…</div>
      </div>
    )
  }

  return (
    <div className="card" data-testid="therapist-attendance-panel">
      <div className="card-header">
        <h3 className="card-title">حضور و غیاب جلسات درمان (فرایند ۶)</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? '…' : 'بروزرسانی'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '0 1rem 1rem', color: 'var(--danger)' }}>{error}</div>
      )}

      <div style={{ padding: '0 1rem 1rem' }}>
        <p style={{ margin: '0 0 0.85rem', fontSize: '0.88rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          پس از برگزاری جلسه، وضعیت <strong>حاضر</strong> یا <strong>غایب</strong> را ثبت کنید.
          ثبت تا پایان همان روز (۲۴:۰۰) امکان‌پذیر است و ویرایش فقط تا ۲۴:۰۰ همان روزِ ثبت باز است.
          برای جلسهٔ پرداخت‌نشده فقط <strong>غیبت</strong> قابل ثبت است (انضباط مالی-آموزشی؛ اولویت حضور بر پرداخت).
        </p>
        <ul style={{ margin: '0 0 0.85rem', paddingInlineStart: '1.15rem', fontSize: '0.82rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          <li>حاضر: +۱ ساعت به فیلد مناسب دوره (۱× / ۲× هفتگی و مجموع)</li>
          <li>غایب موجه: بدون افزایش ساعت</li>
          <li>غایب غیرموجه: تعیین تکلیف هزینه جلسه (فرایند ۷)</li>
          <li>اگر ثبت نکنید، پرونده به مسئول سایت و سپس معاون آموزش اسکیت می‌شود</li>
        </ul>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? 'repeat(2, minmax(0, 1fr))' : 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          <StatTile
            label="نیاز به ثبت"
            value={(stats.needs_recording ?? 0).toLocaleString('fa-IR')}
            tone={stats.needs_recording > 0 ? '#b45309' : '#14532d'}
            bg={stats.needs_recording > 0 ? '#fffbeb' : '#f0fdf4'}
          />
          <StatTile
            label="ثبت‌شده"
            value={(stats.recorded ?? 0).toLocaleString('fa-IR')}
            tone="#1d4ed8"
            bg="#eff6ff"
          />
          <StatTile
            label="بسته / غیرقابل ثبت"
            value={(stats.closed ?? 0).toLocaleString('fa-IR')}
            tone="#64748b"
            bg="#f8fafc"
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.85rem' }}>
          {[
            { id: 'needs_recording', label: 'نیاز به ثبت' },
            { id: 'recorded', label: 'ثبت‌شده' },
            { id: 'closed', label: 'بسته' },
            { id: 'all', label: 'همه' },
          ].map((f) => (
            <button
              key={f.id}
              type="button"
              className={`btn btn-sm ${filter === f.id ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state" style={{ padding: '2rem 1rem' }}>
            <p>{filter === 'needs_recording' ? 'جلسه‌ای برای ثبت حضور و غیاب نیست.' : 'موردی یافت نشد.'}</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {filtered.map((s) => {
              const busy = busyId === s.session_id
              const recorded = s.recorded_status
              const canPresent = Boolean(s.can_record_present)
              const canAbsent = Boolean(s.can_record_absent)
              const showActions = (canPresent || canAbsent) && !recorded
              return (
                <div
                  key={s.session_id}
                  data-testid={`attendance-session-${s.session_id}`}
                  style={{
                    padding: '0.85rem 1rem',
                    borderRadius: '10px',
                    border: s.can_record ? '2px solid #fbbf24' : '1px solid var(--border)',
                    background: s.can_record ? '#fffbeb' : '#fff',
                  }}
                >
                  <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>
                        {fmtDate(s.session_date)}
                        {s.session_number != null && (
                          <span style={{ fontWeight: 500, color: '#64748b', marginRight: '0.35rem' }}>
                            {' '}
                            (جلسه {Number(s.session_number).toLocaleString('fa-IR')})
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.15rem' }}>
                        دانشجو: {formatStudentCodeDisplay(s.student_code)}
                        {' · '}
                        پرداخت: {PAYMENT_FA[s.payment_status] || s.payment_status}
                        {s.attendance_process_state && (
                          <>
                            {' · '}
                            مرحله: {labelState(s.attendance_process_state)}
                          </>
                        )}
                      </div>
                    </div>
                    {recorded && (
                      <span className="badge badge-success" style={{ alignSelf: 'flex-start' }}>
                        {RECORDED_FA[recorded] || recorded}
                      </span>
                    )}
                    {!recorded && s.record_block_reason && (
                      <span className="badge badge-secondary" style={{ alignSelf: 'flex-start' }}>
                        {BLOCK_FA[s.record_block_reason] || s.record_block_reason}
                      </span>
                    )}
                  </div>

                  {showActions && (
                    <div>
                      {s.record_block_reason === 'unpaid' && (
                        <p style={{ margin: '0 0 0.45rem', fontSize: '0.78rem', color: '#b45309', lineHeight: 1.6 }}>
                          جلسه پرداخت‌نشده: دکمهٔ حاضر غیرفعال است؛ فقط غیبت قابل ثبت است.
                        </p>
                      )}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <button
                          type="button"
                          className="btn btn-success btn-sm"
                          disabled={busy || !canPresent}
                          title={!canPresent ? 'برای جلسه پرداخت‌نشده غیرفعال است' : ''}
                          onClick={() => record(s.session_id, 'present')}
                        >
                          {busy ? '…' : '✓ حاضر (+۱ ساعت)'}
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          disabled={busy || !canAbsent}
                          onClick={() => record(s.session_id, 'absent_excused')}
                        >
                          غایب موجه
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          disabled={busy || !canAbsent}
                          onClick={() => record(s.session_id, 'absent_unexcused')}
                        >
                          غایب غیرموجه
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
