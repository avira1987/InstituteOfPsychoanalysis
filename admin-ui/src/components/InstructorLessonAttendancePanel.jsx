import React, { useEffect, useMemo, useState } from 'react'
import { panelApi, processExecApi } from '../services/api'
import { labelState } from '../utils/processDisplay'
import {
  AbsenceCounterTile,
  ClassAttendanceFlowStepper,
  ClassAttendanceHintBlock,
  INSTRUCTOR_STATE_HINTS,
  courseCodeFromInstanceContext,
  isArticleWritingCourse,
  labelAttendanceStatus,
  labelClassAttendanceState,
  resolveClassAttendanceContext,
  todayIsoDate,
} from '../utils/lessonAttendanceDisplay'
import { fmtIsoDate } from '../utils/lessonStartPerTermDisplay'

/**
 * پنل ثبت حضور و غیاب جلسه‌ای — فرایند class_attendance برای مدرس.
 */
export default function InstructorLessonAttendancePanel({
  detail = null,
  availableTransitions = [],
  instanceId = null,
  showToast,
  onRefreshInstance,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const courseCode = useMemo(() => courseCodeFromInstanceContext(ctx), [ctx])
  const lessonCtx = useMemo(() => resolveClassAttendanceContext(ctx), [ctx])
  const isArticle = isArticleWritingCourse(ctx)

  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [sessionDate, setSessionDate] = useState(ctx.session_date || todayIsoDate())
  const [submitting, setSubmitting] = useState(false)

  const submitTransition = availableTransitions.find(
    (t) => t.trigger_event === 'attendance_submitted',
  )

  const isEditable = currentState === 'attendance_list_ready'

  useEffect(() => {
    if (!active || !detail || detail.process_code !== 'class_attendance') return
    if (!isEditable) return
    if (!courseCode) return

    let cancelled = false
    setLoadingRoster(true)
    panelApi.instructorCourseRoster(courseCode)
      .then((res) => {
        if (cancelled) return
        const rows = res.data?.roster || []
        const prefilled = ctx.students_attendance || ctx.attendees
        if (Array.isArray(prefilled) && prefilled.length) {
          const statusById = {}
          prefilled.forEach((r) => {
            if (r?.student_id) statusById[r.student_id] = r.status || 'present'
          })
          setRoster(rows.map((r) => {
            const blocked = Boolean(r.present_blocked)
            const pref = statusById[r.student_id]
            return {
              ...r,
              status: blocked ? 'absent' : (pref || r.status || 'present'),
            }
          }))
        } else {
          setRoster(rows.map((r) => ({
            ...r,
            status: r.present_blocked ? 'absent' : (r.status || 'present'),
          })))
        }
      })
      .catch((e) => {
        if (!cancelled) {
          const msg = e?.response?.data?.detail || e.message || 'خطا در بارگذاری لیست کلاس'
          showToast?.(typeof msg === 'string' ? msg : 'خطا در بارگذاری لیست کلاس', 'error')
          setRoster([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingRoster(false)
      })

    return () => { cancelled = true }
  }, [active, detail, isEditable, courseCode, ctx.students_attendance, ctx.attendees, showToast])

  if (!active || !detail || detail.process_code !== 'class_attendance') {
    return null
  }

  const lessonName = lessonCtx.lessonName
  const teachingAssistant = lessonCtx.teachingAssistant
  const hint = INSTRUCTOR_STATE_HINTS[currentState]
    || 'ثبت حضور و غیاب جلسه کلاس.'

  const recordedRows = lessonCtx.studentsAttendance
  const summary = lessonCtx.summary
  const presentCount = summary.present ?? recordedRows.filter(
    (r) => (r.status || '').toLowerCase() === 'present',
  ).length
  const absentCount = summary.absent ?? recordedRows.filter(
    (r) => ['absent', 'غایب', 'absent_unexcused'].includes(String(r.status || '').toLowerCase()),
  ).length

  const setStatus = (studentId, status) => {
    setRoster((prev) => prev.map((r) => {
      if (r.student_id !== studentId) return r
      if (r.present_blocked) return { ...r, status: 'absent' }
      return { ...r, status }
    }))
  }

  const setAllStatus = (status) => {
    setRoster((prev) => prev.map((r) => {
      if (status === 'present' && r.present_blocked) return { ...r, status: 'absent' }
      return { ...r, status }
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
      const students_attendance = roster.map((r) => ({
        student_id: r.student_id,
        student_name: r.name_fa || r.student_code,
        person_name: r.name_fa || r.student_code,
        role: r.role || 'student',
        status: r.present_blocked ? 'absent' : (r.status || 'present'),
      }))
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: submitTransition.trigger_event,
        payload: {
          session_date: sessionDate,
          course_code: courseCode,
          lesson_name: lessonName,
          course_type: lessonCtx.courseType,
          students_attendance,
        },
        ...(submitTransition.to_state ? { to_state: submitTransition.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('حضور و غیاب جلسه ثبت شد')
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
      data-testid="instructor-lesson-attendance-panel"
      style={{ marginBottom: '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">مدیریت کلاس و حضور و غیاب</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelClassAttendanceState(currentState) || labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <ClassAttendanceFlowStepper currentState={currentState} />

        <ClassAttendanceHintBlock tone={isArticle ? 'warn' : 'info'}>
          {hint}
          {isArticle && (
            <span>
              {' '}
              توجه: در درس مقاله‌نویسی با ۵ غیبت، Incomplete اعمال نمی‌شود ولی گزارش به کمیته نظارت ارسال می‌شود.
            </span>
          )}
        </ClassAttendanceHintBlock>

        <p style={{ fontSize: '0.85rem', lineHeight: 1.65, margin: '0 0 0.75rem', color: '#334155' }}>
          داشبورد مدیریت کلاس:
          {' '}
          <strong>{lessonName}</strong>
          {teachingAssistant ? ` — کمک‌مدرس: ${teachingAssistant}` : ''}
        </p>

        {!isEditable && (
          <div
            data-testid="instructor-attendance-readonly-summary"
            style={{
              padding: '0.85rem 1rem',
              marginBottom: '0.85rem',
              borderRadius: '8px',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              fontSize: '0.85rem',
              lineHeight: 1.65,
            }}
          >
            <div>
              <strong>تاریخ جلسه:</strong>
              {' '}
              {fmtIsoDate(lessonCtx.sessionDate)}
            </div>
            <div>
              <strong>حاضر:</strong>
              {' '}
              {Number(presentCount).toLocaleString('fa-IR')}
              {' '}
              —
              <strong> غایب:</strong>
              {' '}
              {Number(absentCount).toLocaleString('fa-IR')}
            </div>
            {lessonCtx.submittedAt && (
              <div className="muted" style={{ fontSize: '0.8rem', marginTop: '0.35rem' }}>
                ثبت‌شده:
                {' '}
                {fmtIsoDate(lessonCtx.submittedAt)}
              </div>
            )}
            {recordedRows.length > 0 && (
              <div style={{ overflowX: 'auto', marginTop: '0.65rem' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.84rem' }}>
                  <thead>
                    <tr>
                      <th>نام</th>
                      <th>نقش</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recordedRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{row.person_name || row.student_name || '—'}</td>
                        <td>{row.role === 'teaching_assistant' ? 'کمک‌مدرس' : 'دانشجو'}</td>
                        <td>{labelAttendanceStatus(row.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {isEditable && (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.85rem' }}>
              <label style={{ fontSize: '0.85rem' }}>
                <span style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>تاریخ جلسه</span>
                <input
                  type="date"
                  className="form-input"
                  value={sessionDate}
                  onChange={(e) => setSessionDate(e.target.value)}
                  data-testid="instructor-attendance-session-date"
                />
              </label>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  data-testid="instructor-attendance-all-present"
                  onClick={() => setAllStatus('present')}
                  disabled={!roster.length}
                >
                  همه حاضر
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  data-testid="instructor-attendance-all-absent"
                  onClick={() => setAllStatus('absent')}
                  disabled={!roster.length}
                >
                  همه غایب
                </button>
              </div>
            </div>

            {loadingRoster ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری لیست کلاس…</p>
            ) : roster.length === 0 ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>
                هنوز دانشجویی در این درس ثبت‌نام نکرده است.
              </p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '0.85rem' }}>
                {roster.some((r) => r.present_blocked) && (
                  <div
                    data-testid="instructor-attendance-tuition-block-banner"
                    role="status"
                    style={{
                      marginBottom: '0.75rem',
                      padding: '0.65rem 0.85rem',
                      borderRadius: '8px',
                      background: '#fef2f2',
                      borderRight: '4px solid #dc2626',
                      fontSize: '0.82rem',
                      lineHeight: 1.65,
                      color: '#991b1b',
                    }}
                  >
                    برای برخی دانشجویان به‌دلیل قسط معوق، ردیف حضور و غیاب قفل است و فقط «غایب» ثبت می‌شود.
                  </div>
                )}
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>ردیف</th>
                      <th>نام</th>
                      <th>نقش</th>
                      <th>غیبت‌های قبلی</th>
                      <th>حاضر</th>
                      <th>غایب</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roster.map((row, idx) => {
                      const blocked = Boolean(row.present_blocked)
                      const isPresent = !blocked && (row.status || 'present') === 'present'
                      const prevAbs = Number(row.absence_count ?? 0)
                      const warnAbs = prevAbs >= 4
                      const blockReason = row.present_block_reason_fa
                        || 'هشدار: امکان ثبت حضور برای این دانشجو به دلیل عدم تسویه بدهی شهریه وجود ندارد. لطفاً گزینه غیبت را ثبت نمایید.'
                      return (
                        <tr
                          key={row.student_id || idx}
                          data-testid={blocked ? 'attendance-row-installment-locked' : undefined}
                          style={blocked ? { background: '#f1f5f9', color: '#64748b', opacity: 0.92 } : undefined}
                          title={blocked ? blockReason : undefined}
                        >
                          <td>{(idx + 1).toLocaleString('fa-IR')}</td>
                          <td>
                            {row.name_fa || row.student_code || '—'}
                            {blocked && (
                              <>
                                <span
                                  className="badge"
                                  data-testid="attendance-overdue-badge"
                                  style={{
                                    marginRight: '0.4rem',
                                    fontSize: '0.68rem',
                                    background: '#fee2e2',
                                    color: '#991b1b',
                                    border: '1px solid #fecaca',
                                  }}
                                >
                                  قسط معوق
                                </span>
                                <div style={{ fontSize: '0.72rem', color: '#b91c1c', marginTop: '0.2rem', lineHeight: 1.5 }}>
                                  {blockReason}
                                </div>
                              </>
                            )}
                          </td>
                          <td>{row.role === 'teaching_assistant' ? 'کمک‌مدرس' : 'دانشجو'}</td>
                          <td style={{ color: warnAbs ? '#b91c1c' : '#334155', fontWeight: warnAbs ? 700 : 400 }}>
                            {prevAbs.toLocaleString('fa-IR')}
                          </td>
                          <td>
                            <input
                              type="radio"
                              name={`att-${row.student_id}`}
                              checked={isPresent}
                              disabled={blocked}
                              onChange={() => setStatus(row.student_id, 'present')}
                              aria-label={`حاضر — ${row.name_fa || row.student_code}`}
                              title={blocked ? blockReason : undefined}
                            />
                          </td>
                          <td>
                            <input
                              type="radio"
                              name={`att-${row.student_id}`}
                              checked={!isPresent}
                              disabled={blocked}
                              onChange={() => setStatus(row.student_id, 'absent')}
                              aria-label={`غایب — ${row.name_fa || row.student_code}`}
                              title={blocked ? blockReason : undefined}
                            />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {roster.length > 0 && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="instructor-attendance-submit"
                disabled={submitting || !submitTransition || roster.length === 0}
                onClick={handleSubmit}
              >
                {submitting ? 'در حال ثبت…' : 'ثبت حضور و غیاب جلسه'}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}
