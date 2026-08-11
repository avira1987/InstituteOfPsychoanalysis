import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { therapyApi, alocomApi } from '../services/api'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
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
}

function parseSessionDay(iso) {
  if (!iso) return null
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso)
  if (Number.isNaN(d.getTime())) return null
  d.setHours(0, 0, 0, 0)
  return d
}

function sessionCalendarDay(session) {
  return parseSessionDay(session.session_date) || parseSessionDay(session.session_starts_at)
}

function formatWhen(session) {
  const raw = session.session_starts_at || session.session_date
  if (!raw) return 'بدون زمان مشخص'
  return formatShamsiTehran(raw)
}

function mergeSessions(therapyRows, workbenchRows) {
  const wbById = new Map((workbenchRows || []).map((row) => [row.session_id, row]))
  return (therapyRows || []).map((s) => {
    const wb = wbById.get(s.id) || {}
    return {
      ...s,
      session_id: s.id,
      student_code: s.student_code ?? wb.student_code,
      can_record_present: Boolean(wb.can_record_present),
      can_record_absent: Boolean(wb.can_record_absent),
      can_record: Boolean(wb.can_record),
      recorded_status: wb.recorded_status ?? null,
      attendance_process_state: wb.attendance_process_state ?? null,
      record_block_reason: wb.record_block_reason ?? null,
      meeting_url: s.meeting_url || wb.meeting_url || null,
      student_meeting_url_ready: Boolean(
        s.student_meeting_url_ready ?? wb.student_meeting_url_ready,
      ),
    }
  })
}

function SessionCard({
  session,
  draft,
  onFieldChange,
  onSaveNotes,
  onUnlockStudentLink,
  onProvisionAlocom,
  onRecordAttendance,
  busyAction,
}) {
  const sid = session.session_id || session.id
  const row = draft[sid] || {}
  const comment = row.instructor_comment !== undefined
    ? row.instructor_comment
    : (session.instructor_comment || '')
  const score = row.instructor_score !== undefined
    ? row.instructor_score
    : (session.instructor_score ?? '')
  const meetingLink = (session.meeting_url || '').trim()
  const isStubLink = !meetingLink
    || meetingLink.includes('/meet/therapy/')
    || !meetingLink.includes('token=')
  const linkReady = Boolean(meetingLink) && !isStubLink
  const paid = session.payment_status === 'paid' || session.payment_status === 'waived'
  const needsAlocom = !linkReady || session.meeting_provider !== 'alocom'
  const canUnlock = paid && session.student_meeting_url_ready && !session.links_unlocked
  const busy = busyAction === sid

  return (
    <div
      data-testid={`therapist-online-session-${sid}`}
      style={{
        padding: '1rem',
        borderRadius: '10px',
        border: session.can_record ? '2px solid #fbbf24' : '1px solid var(--border)',
        background: session.can_record ? '#fffbeb' : '#fff',
        display: 'grid',
        gap: '0.65rem',
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div>
          <div style={{ fontWeight: 700 }}>
            {formatWhen(session)}
            {session.session_number != null && (
              <span style={{ fontWeight: 500, color: '#64748b', marginRight: '0.35rem' }}>
                {' '}
                (جلسه {Number(session.session_number).toLocaleString('fa-IR')})
              </span>
            )}
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.15rem' }}>
            دانشجو: {formatStudentCodeDisplay(session.student_code)}
            {' · '}
            پرداخت: {PAYMENT_FA[session.payment_status] || session.payment_status}
            {session.attendance_process_state && (
              <>
                {' · '}
                مرحله: {labelState(session.attendance_process_state)}
              </>
            )}
          </div>
        </div>
        {session.recorded_status && (
          <span className="badge badge-success" style={{ alignSelf: 'flex-start' }}>
            {RECORDED_FA[session.recorded_status] || session.recorded_status}
          </span>
        )}
        {!session.recorded_status && session.record_block_reason && (
          <span className="badge badge-secondary" style={{ alignSelf: 'flex-start' }}>
            {BLOCK_FA[session.record_block_reason] || session.record_block_reason}
          </span>
        )}
      </div>

      <OnlineMeetingJoinCta
        mode="online"
        meetingLink={linkReady ? meetingLink : null}
        meetingLinkReady={linkReady}
        meetingLinkIsVisible={linkReady}
        startsAt={session.session_starts_at || session.session_date}
        label="ورود به جلسه (میزبان)"
        allowStaffCopy
        compact
        preparingText="لینک میزبان الوکام هنوز آماده نیست؛ «ایجاد کلاس الوکام» را بزنید یا صفحه را تازه کنید."
      />

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
        {needsAlocom && (
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={busy}
            onClick={() => onProvisionAlocom(session)}
          >
            ایجاد کلاس الوکام
          </button>
        )}
        {canUnlock && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={busy}
            onClick={() => onUnlockStudentLink(session)}
          >
            فعال‌سازی لینک دانشجو
          </button>
        )}
        {paid && session.links_unlocked && linkReady && (
          <span style={{ fontSize: '0.78rem', color: '#166534' }}>لینک دانشجو فعال است</span>
        )}
        {!paid && (
          <span style={{ fontSize: '0.78rem', color: '#b45309' }}>
            لینک دانشجو پس از پرداخت قابل فعال‌سازی است
          </span>
        )}
      </div>

      <div style={{ display: 'grid', gap: '0.45rem' }}>
        <textarea
          className="form-input"
          placeholder="نظر و بازخورد درمانگر (اختیاری)"
          rows={2}
          value={comment}
          onChange={(e) => onFieldChange(sid, 'instructor_comment', e.target.value)}
        />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
          <input
            className="form-input"
            type="number"
            placeholder="نمره (اختیاری)"
            dir="ltr"
            style={{ maxWidth: '120px' }}
            value={score}
            onChange={(e) => onFieldChange(sid, 'instructor_score', e.target.value)}
          />
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={busy}
            onClick={() => onSaveNotes(session)}
          >
            ذخیره نظر
          </button>
        </div>
      </div>

      {(session.can_record_present || session.can_record_absent) && !session.recorded_status && (
        <div>
          <p style={{ margin: '0 0 0.45rem', fontSize: '0.78rem', color: '#64748b', lineHeight: 1.6 }}>
            ثبت حضور و غیاب تا پایان همان روز (۲۴:۰۰) امکان‌پذیر است.
            {session.record_block_reason === 'unpaid' && ' جلسه پرداخت‌نشده: فقط غیبت قابل ثبت است.'}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-success btn-sm"
              disabled={busy || !session.can_record_present}
              title={!session.can_record_present ? 'برای جلسه پرداخت‌نشده غیرفعال است' : ''}
              onClick={() => onRecordAttendance(sid, 'present')}
            >
              {busy ? '…' : '✓ حاضر (+۱ ساعت)'}
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              disabled={busy || !session.can_record_absent}
              onClick={() => onRecordAttendance(sid, 'absent_excused')}
            >
              غایب موجه
            </button>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              disabled={busy || !session.can_record_absent}
              onClick={() => onRecordAttendance(sid, 'absent_unexcused')}
            >
              غایب غیرموجه
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * میزکار جلسات آنلاین درمانگر — کلاس‌های پیش‌رو + ورود الوکام + فعال‌سازی لینک + نظر + حضور/غیاب.
 */
export default function TherapistOnlineSessionsPanel({
  active = true,
  showToast,
  onSessionsLoaded,
  onRecorded,
}) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [draft, setDraft] = useState({})
  const [busyAction, setBusyAction] = useState(null)
  const [filter, setFilter] = useState('upcoming')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [therapySettled, wbSettled] = await Promise.allSettled([
        therapyApi.forTherapist(),
        therapyApi.attendanceWorkbench(),
      ])
      const therapyRows =
        therapySettled.status === 'fulfilled' && Array.isArray(therapySettled.value.data)
          ? therapySettled.value.data
          : []
      const wbSessions =
        wbSettled.status === 'fulfilled'
          ? (wbSettled.value.data?.sessions || [])
          : []
      const wbStats =
        wbSettled.status === 'fulfilled' ? wbSettled.value.data?.stats : null

      if (therapySettled.status === 'rejected' && wbSettled.status === 'rejected') {
        const e = therapySettled.reason
        throw e
      }

      const merged = mergeSessions(therapyRows, wbSessions)
      setSessions(merged)
      onSessionsLoaded?.(merged, wbStats)
      if (therapySettled.status === 'rejected') {
        setError(therapySettled.reason?.response?.data?.detail || 'بارگذاری بخشی از جلسات ممکن نشد.')
      }
    } catch (e) {
      setSessions([])
      setError(e.response?.data?.detail || 'بارگذاری جلسات آنلاین ممکن نشد.')
      onSessionsLoaded?.([], null)
    } finally {
      setLoading(false)
    }
  }, [onSessionsLoaded])

  useEffect(() => {
    if (active) load()
  }, [active, load])

  useEffect(() => {
    if (!active) return undefined
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [active, load])

  const today = useMemo(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  }, [])

  const recentCutoff = useMemo(() => {
    const d = new Date(today)
    d.setDate(d.getDate() - 7)
    return d
  }, [today])

  const filtered = useMemo(() => {
    if (filter === 'all') return sessions
    if (filter === 'needs_recording') {
      return sessions.filter((s) => s.can_record && !s.recorded_status)
    }
    if (filter === 'recent') {
      return sessions.filter((s) => {
        const day = sessionCalendarDay(s)
        return day && day < today && day >= recentCutoff
      })
    }
    return sessions.filter((s) => {
      if (s.status && s.status !== 'scheduled') return false
      const day = sessionCalendarDay(s)
      return day ? day >= today : true
    })
  }, [sessions, filter, today, recentCutoff])

  const upcomingCount = useMemo(
    () => sessions.filter((s) => {
      if (s.status && s.status !== 'scheduled') return false
      const day = sessionCalendarDay(s)
      return day ? day >= today : true
    }).length,
    [sessions, today],
  )

  const setField = (id, field, value) => {
    setDraft((prev) => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }))
  }

  const saveNotes = async (session) => {
    const sid = session.session_id || session.id
    const row = draft[sid] || {}
    const comment = row.instructor_comment !== undefined
      ? row.instructor_comment
      : (session.instructor_comment || '')
    const scoreRaw = row.instructor_score !== undefined
      ? row.instructor_score
      : (session.instructor_score ?? '')
    setBusyAction(sid)
    try {
      const payload = { instructor_comment: comment || null }
      if (scoreRaw !== '' && scoreRaw != null) {
        const n = Number(scoreRaw)
        if (!Number.isNaN(n)) payload.instructor_score = n
      }
      await therapyApi.patchSession(sid, payload)
      showToast?.('نظر ذخیره شد')
      await load()
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'خطا در ذخیره', 'error')
    } finally {
      setBusyAction(null)
    }
  }

  const unlockStudentLink = async (session) => {
    const sid = session.session_id || session.id
    setBusyAction(sid)
    try {
      await therapyApi.patchSession(sid, { links_unlocked: true })
      showToast?.('لینک دانشجو فعال شد')
      await load()
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'فعال‌سازی لینک ممکن نشد', 'error')
    } finally {
      setBusyAction(null)
    }
  }

  const provisionAlocom = async (session) => {
    const sid = session.session_id || session.id
    setBusyAction(sid)
    try {
      await alocomApi.provisionTherapySession(sid, {
        title: `جلسه درمان ${session.session_date || ''}`,
        fetch_student_event_link: true,
      })
      showToast?.('کلاس الوکام ایجاد و لینک‌های میزبان/دانشجو ذخیره شد')
      await load()
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : (e.message || 'خطا در الوکام'), 'error')
    } finally {
      setBusyAction(null)
    }
  }

  const recordAttendance = async (sessionId, attendanceStatus) => {
    setBusyAction(sessionId)
    try {
      await therapyApi.patchSession(sessionId, { attendance_status: attendanceStatus })
      showToast?.('حضور و غیاب ثبت شد')
      await load()
      onRecorded?.()
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : (e.message || 'خطا در ثبت'), 'error')
    } finally {
      setBusyAction(null)
    }
  }

  if (loading && sessions.length === 0) {
    return (
      <div className="card" data-testid="therapist-online-sessions-panel">
        <div style={{ padding: '2rem', textAlign: 'center' }}>در حال بارگذاری جلسات…</div>
      </div>
    )
  }

  return (
    <div className="card" data-testid="therapist-online-sessions-panel">
      <div
        className="card-header"
        style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', justifyContent: 'space-between' }}
      >
        <h3 className="card-title" style={{ margin: 0 }}>جلسات آنلاین — کلاس‌های پیش‌رو</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? '…' : 'تازه‌سازی'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '0 1rem 1rem', color: 'var(--danger)' }}>{error}</div>
      )}

      <div style={{ padding: '0 1rem 1rem' }}>
        <p style={{ margin: '0 0 0.85rem', fontSize: '0.88rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          جلسات برنامه‌ریزی‌شده، ورود میزبان به الوکام، فعال‌سازی لینک دانشجو پس از پرداخت، ثبت نظر و حضور/غیاب طبق فرایند ۶.
          {' '}
          {upcomingCount > 0 && (
            <span>
              {upcomingCount.toLocaleString('fa-IR')}
              {' '}
              جلسهٔ پیش‌رو.
            </span>
          )}
        </p>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.85rem' }}>
          {[
            { id: 'upcoming', label: 'پیش‌رو' },
            { id: 'needs_recording', label: 'نیاز به ثبت' },
            { id: 'recent', label: '۷ روز اخیر' },
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
            <p>
              {filter === 'upcoming'
                ? 'جلسهٔ پیش‌رویی در تقویم شما ثبت نشده است.'
                : 'موردی یافت نشد.'}
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {filtered.map((session) => (
              <SessionCard
                key={session.session_id || session.id}
                session={session}
                draft={draft}
                onFieldChange={setField}
                onSaveNotes={saveNotes}
                onUnlockStudentLink={unlockStudentLink}
                onProvisionAlocom={provisionAlocom}
                onRecordAttendance={recordAttendance}
                busyAction={busyAction}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
