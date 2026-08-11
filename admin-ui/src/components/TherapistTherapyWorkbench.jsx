import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { therapyApi, alocomApi } from '../services/api'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
import TherapistAttendancePanel from './TherapistAttendancePanel'
import { HintBlock } from '../utils/attendanceChainDisplay'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { formatStudentCodeDisplay, labelState } from '../utils/processDisplay'

const PAYMENT_FA = {
  pending: 'پرداخت نشده',
  paid: 'پرداخت‌شده',
  waived: 'معاف',
}

const COURSE_FA = {
  comprehensive: 'جامع',
  introductory: 'آشنایی',
}

const RECORDED_FA = {
  present: 'حاضر (+۱ ساعت)',
  absent_excused: 'غایب موجه',
  absent_unexcused: 'غایب غیرموجه',
}

const BLOCK_FA = {
  session_cancelled: 'جلسه کنسل شده — ثبت بسته',
  unpaid: 'پرداخت نشده — فقط غیبت قابل ثبت',
  already_recorded: 'قبلاً ثبت شده',
  recording_closed: 'ثبت بسته (وقفه یا کنسلی)',
  auto_absence_unpaid: 'غیبت خودکار (پرداخت نشده)',
  session_completed: 'جلسه تکمیل شده (+۱ ساعت)',
  excused_absence: 'غیبت موجه ثبت شد',
  unexcused_absence: 'غیبت غیرموجه — تعیین تکلیف هزینه',
  quota_exceeded: 'سهمیه غیبت تمام شد',
}

const FILTER_OPTIONS = [
  { id: 'needs_recording', label: 'نیاز ثبت حضور' },
  { id: 'needs_action', label: 'نیاز اقدام' },
  { id: 'today', label: 'امروز' },
  { id: 'week', label: 'هفته' },
  { id: '', label: 'همهٔ منتسب‌ها' },
  { id: 'missing_future', label: 'بدون جلسه آینده' },
]

function hourBucketHint(weeklySessions) {
  const n = Number(weeklySessions) || 1
  if (n >= 2) {
    return 'در صورت حضور، +۱ ساعت به فیلد «دو بار در هفته» و مجموع ساعات اضافه می‌شود.'
  }
  return 'در صورت حضور، +۱ ساعت به فیلد «یک‌بار در هفته» و مجموع ساعات اضافه می‌شود.'
}

function formatWhen(session) {
  const raw = session.session_starts_at || session.session_date
  if (!raw) return 'بدون زمان مشخص'
  return formatShamsiTehran(raw)
}

function meetingLinkReady(session) {
  const meetingLink = (session.meeting_url || '').trim()
  const isStubLink = !meetingLink
    || meetingLink.includes('/meet/therapy/')
    || !meetingLink.includes('token=')
  return Boolean(meetingLink) && !isStubLink
}

function StudentBadges({ row }) {
  const badges = []
  if (row.needs_recording > 0) {
    badges.push({ key: 'rec', text: `ثبت حضور (${row.needs_recording})`, tone: '#b45309', bg: '#fffbeb' })
  }
  if (row.missing_future_schedule) {
    badges.push({ key: 'miss', text: 'بدون جلسه آینده', tone: '#b91c1c', bg: '#fef2f2' })
  }
  if (row.unpaid_upcoming > 0) {
    badges.push({ key: 'pay', text: `پرداخت نشده (${row.unpaid_upcoming})`, tone: '#1d4ed8', bg: '#eff6ff' })
  }
  if (!badges.length) {
    return <span style={{ fontSize: '0.75rem', color: '#64748b' }}>بدون اقدام فوری</span>
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
      {badges.map((b) => (
        <span
          key={b.key}
          style={{
            fontSize: '0.72rem',
            padding: '0.15rem 0.45rem',
            borderRadius: '6px',
            background: b.bg,
            color: b.tone,
            fontWeight: 600,
          }}
        >
          {b.text}
        </span>
      ))}
    </div>
  )
}

function SessionRow({
  session,
  draft,
  busyId,
  weeklySessions,
  courseType,
  onFieldChange,
  onSaveNotes,
  onUnlockStudentLink,
  onProvisionAlocom,
  onRecord,
}) {
  const sid = session.session_id
  const busy = busyId === sid
  const row = draft[sid] || {}
  const comment = row.instructor_comment !== undefined
    ? row.instructor_comment
    : (session.instructor_comment || '')
  const score = row.instructor_score !== undefined
    ? row.instructor_score
    : (session.instructor_score ?? '')
  const linkReady = meetingLinkReady(session)
  const meetingLink = (session.meeting_url || '').trim()
  const paid = session.payment_status === 'paid' || session.payment_status === 'waived'
  const needsAlocom = !linkReady || session.meeting_provider !== 'alocom'
  const canUnlock = paid && session.student_meeting_url_ready && !session.links_unlocked
  const showAttendanceActions = (session.can_record_present || session.can_record_absent)
    && !session.recorded_status
  const courseLabel = COURSE_FA[courseType] || courseType || '—'

  return (
    <div
      data-testid={`workbench-session-${sid}`}
      style={{
        padding: '0.85rem',
        borderRadius: '8px',
        border: session.can_record ? '1px solid #fbbf24' : '1px solid var(--border)',
        background: session.can_record ? '#fffbeb' : '#fafafa',
        display: 'grid',
        gap: '0.55rem',
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '0.35rem' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
            {formatWhen(session)}
            {session.session_number != null && (
              <span style={{ fontWeight: 500, color: '#64748b', marginRight: '0.35rem' }}>
                {' '}
                (جلسه {Number(session.session_number).toLocaleString('fa-IR')})
              </span>
            )}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            پرداخت: {PAYMENT_FA[session.payment_status] || session.payment_status}
            {' · '}
            دوره: {courseLabel}
            {' · '}
            جلسات هفتگی: {(Number(weeklySessions) || 1).toLocaleString('fa-IR')}
            {session.attendance_process_state && (
              <> · مرحله: {labelState(session.attendance_process_state)}</>
            )}
          </div>
        </div>
        {session.recorded_status && (
          <span className="badge badge-success">
            {RECORDED_FA[session.recorded_status] || session.recorded_status}
          </span>
        )}
        {!session.recorded_status && session.record_block_reason && (
          <span className="badge badge-secondary">
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

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', alignItems: 'center' }}>
        {needsAlocom && (
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={busy}
            data-testid={`workbench-provision-alocom-${sid}`}
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
            data-testid={`workbench-unlock-student-link-${sid}`}
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

      <div style={{ display: 'grid', gap: '0.4rem' }}>
        <textarea
          className="form-input"
          placeholder="نظر و بازخورد درمانگر (اختیاری)"
          rows={2}
          value={comment}
          onChange={(e) => onFieldChange(sid, 'instructor_comment', e.target.value)}
        />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', alignItems: 'center' }}>
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

      <div
        data-testid={`workbench-attendance-sop-${sid}`}
        style={{
          padding: '0.75rem',
          borderRadius: '8px',
          background: showAttendanceActions ? '#fff7ed' : '#fff',
          border: showAttendanceActions ? '1px solid #fdba74' : '1px dashed var(--border)',
          display: 'grid',
          gap: '0.5rem',
        }}
      >
        <div style={{ fontWeight: 700, fontSize: '0.86rem' }}>
          ثبت حضور و غیاب (فرایند ۶)
        </div>

        {showAttendanceActions && (
          <HintBlock
            testId={`workbench-attendance-hint-${sid}`}
            title="دستورالعمل SOP"
            color="#b45309"
            bg="#fffbeb"
          >
            <ul style={{ margin: 0, paddingInlineStart: '1.1rem' }}>
              <li>صرف پرداخت به‌معنای گذراندن ساعت نیست؛ فقط تأیید حضور توسط شما ساعت را اضافه می‌کند.</li>
              <li>ثبت تا پایان همان روز (۲۴:۰۰) و ویرایش فقط تا ۲۴:۰۰ همان روزِ ثبت.</li>
              <li>{hourBucketHint(weeklySessions)}</li>
              <li>غایب موجه: بدون افزایش ساعت. غایب غیرموجه: تعیین تکلیف هزینه (فرایند ۷).</li>
            </ul>
          </HintBlock>
        )}

        {session.record_block_reason === 'unpaid' && showAttendanceActions && (
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#b45309', lineHeight: 1.6 }}>
            جلسه پرداخت‌نشده: دکمهٔ «حاضر» غیرفعال است؛ فقط ثبت غیبت مجاز است (انضباط مالی-آموزشی).
          </p>
        )}

        {(session.record_block_reason === 'recording_closed'
          || session.record_block_reason === 'session_cancelled') && (
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b', lineHeight: 1.6 }}>
            پیش‌بررسی SOP: وقفه یا کنسلی — امکان ثبت حضور/غیاب بسته است.
          </p>
        )}

        {session.recorded_status && (
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#166534', lineHeight: 1.6 }}>
            وضعیت ثبت‌شده: {RECORDED_FA[session.recorded_status] || session.recorded_status}
            {session.recorded_status === 'present' && ` — ${hourBucketHint(weeklySessions)}`}
            {session.recorded_status === 'absent_unexcused' && ' — فرایند تعیین تکلیف هزینه آغاز می‌شود.'}
          </p>
        )}

        {showAttendanceActions ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            <button
              type="button"
              className="btn btn-success btn-sm"
              disabled={busy || !session.can_record_present}
              title={!session.can_record_present ? 'برای جلسه پرداخت‌نشده غیرفعال است' : 'حضور — +۱ ساعت آموزشی'}
              data-testid={`workbench-record-present-${sid}`}
              onClick={() => onRecord(sid, 'present')}
            >
              {busy ? '…' : '✓ حاضر (+۱ ساعت)'}
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              disabled={busy || !session.can_record_absent}
              title="غیبت موجه — بدون افزایش ساعت"
              data-testid={`workbench-record-excused-${sid}`}
              onClick={() => onRecord(sid, 'absent_excused')}
            >
              غایب موجه
            </button>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              disabled={busy || !session.can_record_absent}
              title="غیبت غیرموجه — تعیین تکلیف هزینه"
              data-testid={`workbench-record-unexcused-${sid}`}
              onClick={() => onRecord(sid, 'absent_unexcused')}
            >
              غایب غیرموجه
            </button>
          </div>
        ) : !session.recorded_status && !session.record_block_reason && (
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b', lineHeight: 1.6 }}>
            هنوز زمان ثبت فرا نرسیده است. پس از موعد جلسه، دکمه‌های حاضر/غایب اینجا فعال می‌شوند.
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * میزکار مقیاس‌پذیر درمان — یک ردیف به‌ازای دانشجو + drill-down جلسات + ورود الوکام.
 */
export default function TherapistTherapyWorkbench({
  active = true,
  showToast,
  onTotalsLoaded,
  initialFilter = '',
  roleScope = 'therapist',
}) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState(initialFilter)
  const [expandedId, setExpandedId] = useState(null)
  const [sessionPages, setSessionPages] = useState({})
  const [sessionLoading, setSessionLoading] = useState(null)
  const [busyRepair, setBusyRepair] = useState(null)
  const [busyAction, setBusyAction] = useState(null)
  const [draft, setDraft] = useState({})
  const [attendanceRefreshKey, setAttendanceRefreshKey] = useState(0)
  // جلوگیری از حلقهٔ بی‌نهایت: والد معمولاً onTotalsLoaded اینلاین می‌دهد
  const onTotalsLoadedRef = useRef(onTotalsLoaded)
  onTotalsLoadedRef.current = onTotalsLoaded

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {
        role_scope: roleScope,
        limit: 100,
        offset: 0,
      }
      if (filter) params.filter = filter
      if (search.trim()) params.q = search.trim()
      const res = await therapyApi.workbenchSummary(params)
      setSummary(res.data)
      onTotalsLoadedRef.current?.(res.data?.totals || null)
    } catch (e) {
      setSummary(null)
      setError(e.response?.data?.detail || 'بارگذاری میزکار ممکن نشد.')
      onTotalsLoadedRef.current?.(null)
    } finally {
      setLoading(false)
    }
  }, [filter, search, roleScope])

  useEffect(() => {
    if (!active) return undefined
    const delay = search.trim() ? 300 : 0
    const timer = setTimeout(() => {
      loadSummary()
    }, delay)
    return () => clearTimeout(timer)
  }, [active, loadSummary, search])

  useEffect(() => {
    if (initialFilter !== filter) setFilter(initialFilter || '')
    // فقط وقتی لینک عمیق filter را عوض می‌کند؛ نه روی هر بارگذاری خلاصه
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFilter])

  const loadStudentSessions = useCallback(async (studentId, page = 1) => {
    setSessionLoading(studentId)
    try {
      const res = await therapyApi.workbenchSessions({
        student_id: studentId,
        role_scope: roleScope,
        page,
        page_size: 15,
        needs_recording: filter === 'needs_recording' ? true : undefined,
      })
      setSessionPages((prev) => ({
        ...prev,
        [studentId]: res.data,
      }))
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'بارگذاری جلسات ممکن نشد.', 'error')
    } finally {
      setSessionLoading(null)
    }
  }, [filter, roleScope, showToast])

  const toggleExpand = (studentId) => {
    if (expandedId === studentId) {
      setExpandedId(null)
      return
    }
    setExpandedId(studentId)
    if (!sessionPages[studentId]) {
      loadStudentSessions(studentId, 1)
    }
  }

  const handleRepair = async (studentId) => {
    setBusyRepair(studentId)
    try {
      const res = await therapyApi.workbenchRepair(studentId)
      const created = res.data?.seed?.created ?? 0
      showToast?.(
        created > 0
          ? `${created.toLocaleString('fa-IR')} جلسه تا پایان ترم ساخته شد.`
          : 'تقویم بررسی شد؛ جلسهٔ جدیدی لازم نبود.',
      )
      await loadSummary()
      if (expandedId === studentId) {
        await loadStudentSessions(studentId, 1)
      }
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'تکمیل تقویم ممکن نشد.', 'error')
    } finally {
      setBusyRepair(null)
    }
  }

  const refreshExpandedSessions = async () => {
    if (!expandedId) return
    const page = sessionPages[expandedId]?.pagination?.page || 1
    await loadStudentSessions(expandedId, page)
  }

  const setField = (id, field, value) => {
    setDraft((prev) => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }))
  }

  const handleSaveNotes = async (session) => {
    const sid = session.session_id
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
      await refreshExpandedSessions()
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'خطا در ذخیره', 'error')
    } finally {
      setBusyAction(null)
    }
  }

  const handleUnlockStudentLink = async (session) => {
    const sid = session.session_id
    setBusyAction(sid)
    try {
      await therapyApi.patchSession(sid, { links_unlocked: true })
      showToast?.('لینک دانشجو فعال شد')
      await refreshExpandedSessions()
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'فعال‌سازی لینک ممکن نشد', 'error')
    } finally {
      setBusyAction(null)
    }
  }

  const handleProvisionAlocom = async (session) => {
    const sid = session.session_id
    setBusyAction(sid)
    try {
      await alocomApi.provisionTherapySession(sid, {
        title: `جلسه درمان ${session.session_date || ''}`,
        fetch_student_event_link: true,
      })
      showToast?.('کلاس الوکام ایجاد و لینک‌های میزبان/دانشجو ذخیره شد')
      await refreshExpandedSessions()
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : (e.message || 'خطا در الوکام'), 'error')
    } finally {
      setBusyAction(null)
    }
  }

  const handleRecord = async (sessionId, status) => {
    setBusyAction(sessionId)
    try {
      await therapyApi.patchSession(sessionId, { attendance_status: status })
      showToast?.('حضور و غیاب ثبت شد.')
      await loadSummary()
      await refreshExpandedSessions()
      setAttendanceRefreshKey((k) => k + 1)
    } catch (e) {
      showToast?.(e.response?.data?.detail || 'ثبت حضور ممکن نشد.', 'error')
    } finally {
      setBusyAction(null)
    }
  }

  const handleAttendancePanelRecorded = useCallback(async () => {
    await loadSummary()
    setExpandedId((currentExpanded) => {
      if (currentExpanded) {
        loadStudentSessions(currentExpanded, 1)
      }
      return currentExpanded
    })
  }, [loadSummary, loadStudentSessions])

  const students = summary?.students || []
  const totals = summary?.totals

  const statTiles = useMemo(() => {
    if (!totals) return []
    return [
      { label: 'دانشجو', value: totals.students, tone: '#14532d' },
      { label: 'نیاز ثبت', value: totals.needs_recording, tone: '#b45309' },
      { label: 'بدون جلسه آینده', value: totals.missing_future_schedule, tone: '#b91c1c' },
      { label: 'جلسات پیش‌رو', value: totals.upcoming_sessions, tone: '#1d4ed8' },
    ]
  }, [totals])

  if (!active) return null

  return (
    <div data-testid="therapist-therapy-workbench" style={{ display: 'grid', gap: '1rem' }}>
      {roleScope === 'therapist' && (
        <TherapistAttendancePanel
          key={attendanceRefreshKey}
          active={active}
          showToast={showToast}
          onRecorded={handleAttendancePanelRecorded}
          compact
        />
      )}

      {statTiles.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
          }}
        >
          {statTiles.map((t) => (
            <div
              key={t.label}
              style={{
                padding: '0.65rem 0.75rem',
                borderRadius: '8px',
                background: '#f8fafc',
                borderRight: `3px solid ${t.tone}`,
              }}
            >
              <div style={{ fontSize: '0.72rem', color: '#64748b' }}>{t.label}</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: t.tone }}>
                {Number(t.value).toLocaleString('fa-IR')}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ padding: '1rem' }}>
        <p style={{ margin: '0 0 0.85rem', fontSize: '0.88rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          دانشجو را باز کنید تا جلسات، ورود الوکام، فعال‌سازی لینک دانشجو، و ثبت حضور/غیاب طبق SOP فرایند ۶ را ببینید.
          صف بالای صفحه جلسات نیازمند ثبت را یک‌جا نشان می‌دهد.
        </p>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.5rem',
            alignItems: 'center',
            marginBottom: '0.75rem',
          }}
        >
          <input
            type="text"
            className="form-input"
            placeholder="جستجوی کد دانشجو…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ maxWidth: '200px' }}
          />
          <button type="button" className="btn btn-outline btn-sm" onClick={loadSummary}>
            جستجو
          </button>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginRight: 'auto' }}>
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.id || 'all'}
                type="button"
                className={`btn btn-sm ${filter === opt.id ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setFilter(opt.id)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <div className="loading-spinner" />
          </div>
        )}
        {!loading && error && (
          <div className="alert alert-danger">{error}</div>
        )}
        {!loading && !error && students.length === 0 && (
          <div className="empty-state" style={{ padding: '2rem' }}>
            <p>دانشجویی در این فیلتر یافت نشد.</p>
          </div>
        )}
        {!loading && !error && students.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {students.map((row) => {
              const expanded = expandedId === row.student_id
              const sessionsData = sessionPages[row.student_id]
              return (
                <div
                  key={row.student_id}
                  data-testid={`workbench-student-${row.student_id}`}
                  style={{
                    border: expanded ? '2px solid var(--primary)' : '1px solid var(--border)',
                    borderRadius: '10px',
                    overflow: 'hidden',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => toggleExpand(row.student_id)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      flexWrap: 'wrap',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.75rem 1rem',
                      background: expanded ? 'var(--primary-light, #eff6ff)' : '#fff',
                      border: 'none',
                      cursor: 'pointer',
                      textAlign: 'right',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700 }}>
                        {formatStudentCodeDisplay(row.student_code)}
                        {row.course_type && (
                          <span
                            className={`badge ${row.course_type === 'comprehensive' ? 'badge-primary' : 'badge-info'}`}
                            style={{ marginRight: '0.45rem', fontSize: '0.65rem' }}
                          >
                            {COURSE_FA[row.course_type] || row.course_type}
                          </span>
                        )}
                      </div>
                      <StudentBadges row={row} />
                      <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                        جلسات هفتگی: {(Number(row.weekly_sessions) || 1).toLocaleString('fa-IR')}
                        {row.next_session_date && (
                          <>
                            {' · '}
                            جلسه بعدی: {formatShamsiTehran(row.next_session_starts_at || row.next_session_date)}
                          </>
                        )}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                      {row.missing_future_schedule && (
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          disabled={busyRepair === row.student_id}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRepair(row.student_id)
                          }}
                        >
                          {busyRepair === row.student_id ? '…' : 'تکمیل تقویم ترم'}
                        </button>
                      )}
                      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                        {expanded ? '▲' : '▼'}
                      </span>
                    </div>
                  </button>
                  {expanded && (
                    <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid var(--border)', background: '#fafafa' }}>
                      {sessionLoading === row.student_id && (
                        <div style={{ textAlign: 'center', padding: '1rem' }}>
                          <div className="loading-spinner" />
                        </div>
                      )}
                      {sessionLoading !== row.student_id && sessionsData && (
                        <>
                          <div style={{ display: 'grid', gap: '0.5rem' }}>
                            {(sessionsData.sessions || []).map((sess) => (
                              <SessionRow
                                key={sess.session_id}
                                session={sess}
                                draft={draft}
                                busyId={busyAction}
                                weeklySessions={row.weekly_sessions}
                                courseType={row.course_type}
                                onFieldChange={setField}
                                onSaveNotes={handleSaveNotes}
                                onUnlockStudentLink={handleUnlockStudentLink}
                                onProvisionAlocom={handleProvisionAlocom}
                                onRecord={handleRecord}
                              />
                            ))}
                          </div>
                          {(sessionsData.sessions || []).length === 0 && (
                            <p style={{ fontSize: '0.85rem', color: '#64748b' }}>جلسه‌ای در این بازه نیست.</p>
                          )}
                          {sessionsData.pagination && sessionsData.pagination.pages > 1 && (
                            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', justifyContent: 'center' }}>
                              <button
                                type="button"
                                className="btn btn-outline btn-sm"
                                disabled={(sessionsData.pagination.page || 1) <= 1}
                                onClick={() => loadStudentSessions(row.student_id, (sessionsData.pagination.page || 1) - 1)}
                              >
                                قبلی
                              </button>
                              <span style={{ fontSize: '0.8rem', alignSelf: 'center' }}>
                                صفحه {(sessionsData.pagination.page || 1).toLocaleString('fa-IR')}
                                {' '}
                                از {sessionsData.pagination.pages.toLocaleString('fa-IR')}
                              </span>
                              <button
                                type="button"
                                className="btn btn-outline btn-sm"
                                disabled={(sessionsData.pagination.page || 1) >= sessionsData.pagination.pages}
                                onClick={() => loadStudentSessions(row.student_id, (sessionsData.pagination.page || 1) + 1)}
                              >
                                بعدی
                              </button>
                            </div>
                          )}
                        </>
                      )}
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
