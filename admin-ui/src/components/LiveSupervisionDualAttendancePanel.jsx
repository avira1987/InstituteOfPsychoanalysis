import React, { useEffect, useMemo, useState } from 'react'
import { panelApi, processExecApi } from '../services/api'
import { labelState } from '../utils/processDisplay'
import {
  courseCodeFromInstanceContext,
  todayIsoDate,
} from '../utils/lessonAttendanceDisplay'
import { HintBlock } from '../utils/liveSupervisionCourseCompletionDisplay'

/**
 * ثبت حضور دوگانه (عادی / پشت‌آینه) — class_attendance با course_type=live_supervision.
 */
export default function LiveSupervisionDualAttendancePanel({
  detail = null,
  availableTransitions = [],
  instanceId = null,
  showToast,
  onRefreshInstance,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const courseType = (ctx.course_type || '').toLowerCase()
  const isLiveSupervision = courseType === 'live_supervision' || ctx.live_supervision_session
  const courseCode = useMemo(() => courseCodeFromInstanceContext(ctx), [ctx])

  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [sessionDate, setSessionDate] = useState(ctx.session_date || todayIsoDate())
  const [submitting, setSubmitting] = useState(false)

  const submitTransition = availableTransitions.find(
    (t) => t.trigger_event === 'attendance_submitted',
  )

  useEffect(() => {
    if (!active || !detail || detail.process_code !== 'class_attendance') return
    if (!isLiveSupervision) return
    if (currentState !== 'attendance_list_ready') return
    if (!courseCode) return

    let cancelled = false
    setLoadingRoster(true)
    Promise.all([
      panelApi.instructorCourseRoster(courseCode),
      panelApi.liveSupervisionProgress(courseCode).catch(() => ({ data: { progress: [] } })),
    ])
      .then(([rosterRes, progRes]) => {
        if (cancelled) return
        const rows = rosterRes.data?.roster || []
        const progress = progRes.data?.progress || []
        const progById = {}
        progress.forEach((p) => {
          if (p?.student_id) progById[p.student_id] = p
        })
        setRoster(rows.map((r) => ({
          ...r,
          normal_present: false,
          mirror_present: false,
          normal_count: progById[r.student_id]?.normal_count ?? 0,
          mirror_count: progById[r.student_id]?.mirror_count ?? 0,
          admission_cohort: progById[r.student_id]?.admission_cohort,
        })))
      })
      .catch((e) => {
        if (!cancelled) {
          const msg = e?.response?.data?.detail || e.message || 'خطا در بارگذاری لیست'
          showToast?.(typeof msg === 'string' ? msg : 'خطا در بارگذاری لیست', 'error')
          setRoster([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingRoster(false)
      })

    return () => { cancelled = true }
  }, [active, detail, isLiveSupervision, currentState, courseCode, showToast])

  if (!active || !detail || detail.process_code !== 'class_attendance' || !isLiveSupervision) {
    return null
  }
  if (currentState !== 'attendance_list_ready') return null

  const lessonName = ctx.lesson_name || courseCode || 'سوپرویژن زنده'

  const setField = (studentId, field, value) => {
    setRoster((prev) => prev.map((r) => {
      if (r.student_id !== studentId) return r
      const next = { ...r, [field]: value }
      if (field === 'normal_present' && value) next.mirror_present = false
      if (field === 'mirror_present' && value) next.normal_present = false
      if (field === 'absent' && value) {
        next.normal_present = false
        next.mirror_present = false
      }
      return next
    }))
  }

  const handleSubmit = async () => {
    if (!submitTransition || !instanceId) {
      showToast?.('اقدام ثبت حضور در دسترس نیست.', 'error')
      return
    }
    if (!roster.length) {
      showToast?.('لیست کلاس خالی است.', 'error')
      return
    }
    setSubmitting(true)
    try {
      const dual_attendance = roster.map((r) => {
        const absent = !r.normal_present && !r.mirror_present
        return {
          student_id: r.student_id,
          student_name: r.name_fa || r.student_code,
          normal_present: !!r.normal_present,
          mirror_present: !!r.mirror_present,
          absent,
        }
      })
      const students_attendance = roster.map((r) => ({
        student_id: r.student_id,
        student_name: r.name_fa || r.student_code,
        person_name: r.name_fa || r.student_code,
        role: r.role || 'student',
        status: (!r.normal_present && !r.mirror_present) ? 'absent' : 'present',
        mirror_present: !!r.mirror_present,
      }))
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: submitTransition.trigger_event,
        payload: {
          session_date: sessionDate,
          course_code: courseCode,
          course_type: 'live_supervision',
          live_supervision_session: true,
          lesson_name: lessonName,
          students_attendance,
          dual_attendance,
        },
        ...(submitTransition.to_state ? { to_state: submitTransition.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('حضور دوگانه جلسه ثبت شد')
        onRefreshInstance?.()
      } else {
        showToast?.(res.data?.error || 'خطا در ثبت حضور', 'error')
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'خطا در ثبت حضور'
      showToast?.(typeof msg === 'string' ? msg : 'خطا در ثبت حضور', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="card"
      data-testid="live-supervision-dual-attendance-panel"
      style={{ marginBottom: '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">حضور دوگانه سوپرویژن زنده</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <HintBlock tone="info">
          برای هر دانشجو یکی از سه حالت را انتخاب کنید: حضور عادی، حضور پشت‌آینه، یا غایب.
          ترتیب لیست بر اساس اولویت SOP (ورودی قدیمی‌تر و تجربه بالینی بیشتر) است.
        </HintBlock>

        <p style={{ fontSize: '0.85rem', margin: '0 0 0.75rem' }}>
          درس:
          {' '}
          <strong>{lessonName}</strong>
        </p>

        <label style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.85rem' }}>
          <span style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>تاریخ جلسه</span>
          <input
            type="date"
            className="form-input"
            value={sessionDate}
            onChange={(e) => setSessionDate(e.target.value)}
            data-testid="live-supervision-session-date"
          />
        </label>

        {loadingRoster ? (
          <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری لیست کلاس…</p>
        ) : roster.length === 0 ? (
          <p className="muted" style={{ fontSize: '0.85rem' }}>لیست کلاس خالی است.</p>
        ) : (
          <div style={{ overflowX: 'auto', marginBottom: '0.85rem' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.84rem' }}>
              <thead>
                <tr>
                  <th>ردیف</th>
                  <th>نام</th>
                  <th>عادی</th>
                  <th>پشت‌آینه</th>
                  <th>غایب</th>
                  <th>۱۵+۳</th>
                </tr>
              </thead>
              <tbody>
                {roster.map((row, idx) => {
                  const absent = !row.normal_present && !row.mirror_present
                  return (
                    <tr key={row.student_id || idx}>
                      <td>{(idx + 1).toLocaleString('fa-IR')}</td>
                      <td>
                        {row.name_fa || row.student_code || '—'}
                        {row.admission_cohort != null && (
                          <span style={{ fontSize: '0.75rem', color: '#64748b', marginRight: '0.35rem' }}>
                            (ورودی {row.admission_cohort})
                          </span>
                        )}
                      </td>
                      <td>
                        <input
                          type="radio"
                          name={`ls-n-${row.student_id}`}
                          checked={!!row.normal_present}
                          onChange={() => setField(row.student_id, 'normal_present', true)}
                        />
                      </td>
                      <td>
                        <input
                          type="radio"
                          name={`ls-m-${row.student_id}`}
                          checked={!!row.mirror_present}
                          onChange={() => setField(row.student_id, 'mirror_present', true)}
                        />
                      </td>
                      <td>
                        <input
                          type="radio"
                          name={`ls-a-${row.student_id}`}
                          checked={absent}
                          onChange={() => {
                            setField(row.student_id, 'normal_present', false)
                            setField(row.student_id, 'mirror_present', false)
                          }}
                        />
                      </td>
                      <td style={{ fontSize: '0.78rem' }}>
                        {Number(row.normal_count || 0).toLocaleString('fa-IR')}
                        +
                        {Number(row.mirror_count || 0).toLocaleString('fa-IR')}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary btn-sm"
          data-testid="live-supervision-attendance-submit"
          disabled={submitting || !submitTransition || roster.length === 0}
          onClick={handleSubmit}
        >
          {submitting ? 'در حال ثبت…' : 'ثبت حضور دوگانه جلسه'}
        </button>
      </div>
    </div>
  )
}
