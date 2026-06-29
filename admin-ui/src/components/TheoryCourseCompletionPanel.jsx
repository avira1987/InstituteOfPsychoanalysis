import React, { useEffect, useMemo, useState } from 'react'
import { panelApi, processExecApi } from '../services/api'
import {
  PROCESS_CODE,
  PROCESS_TITLE_FA,
  EXAM_MAX,
  PARTICIPATION_MAX,
  STATE_HINTS,
  TheoryFlowStepper,
  TheoryHintBlock,
  TheorySlaBanner,
  InfoTile,
  buildSession18Payload,
  computeAttendanceScore,
  computeTotalScore,
  isTerminalState,
  labelBorderlineStatus,
  labelGrade,
  labelPassFail,
  labelTheoryState,
  resolveTheoryCompletionContext,
  rosterRowToSession18Row,
  scoringSummaryLabel,
  validateExamPackId,
  validateParticipation,
} from '../utils/theoryCourseCompletionDisplay'

/**
 * داشبورد مدرس — خاتمه دروس تئوری — فرایند SOP ۶۱.
 */
export default function TheoryCourseCompletionPanel({
  detail = null,
  availableTransitions = [],
  instanceId = null,
  showToast,
  onRefreshInstance,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const theoryCtx = useMemo(() => resolveTheoryCompletionContext(ctx), [ctx])
  const courseCode = theoryCtx.courseCode

  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [examPackId, setExamPackId] = useState(ctx.exam_pack_id || '')

  const prefilledById = useMemo(() => {
    const map = {}
    ;(theoryCtx.studentsGrades || []).forEach((row) => {
      if (row?.student_id) map[String(row.student_id)] = row
    })
    return map
  }, [theoryCtx.studentsGrades])

  useEffect(() => {
    if (!active || !detail || detail.process_code !== PROCESS_CODE) return
    if (!['session_18_entry', 'qualitative_eval_pending', 'final_exam_open', 'grades_computed'].includes(currentState)) {
      if (theoryCtx.studentsGrades.length) {
        setRoster(theoryCtx.studentsGrades.map((g) => rosterRowToSession18Row(g, prefilledById)))
      }
      return
    }

    let cancelled = false
    setLoadingRoster(true)

    if (courseCode) {
      panelApi.theoryCourseGradesPreview(courseCode, instanceId)
        .then((res) => {
          if (cancelled) return
          const apiRows = res.data?.students_grades || []
          setRoster(apiRows.map((r) => rosterRowToSession18Row(r, prefilledById)))
          if (res.data?.exam_pack_id && !examPackId) {
            setExamPackId(res.data.exam_pack_id)
          }
        })
        .catch(() => {
          if (cancelled) return
          panelApi.instructorCourseRoster(courseCode)
            .then((res) => {
              if (cancelled) return
              const rows = res.data?.roster || []
              setRoster(rows.map((r) => rosterRowToSession18Row(r, prefilledById)))
            })
            .catch(() => { if (!cancelled) setRoster([]) })
        })
        .finally(() => { if (!cancelled) setLoadingRoster(false) })
    } else if (theoryCtx.studentsGrades.length) {
      setRoster(theoryCtx.studentsGrades.map((g) => rosterRowToSession18Row(g, prefilledById)))
      setLoadingRoster(false)
    } else {
      setRoster([])
      setLoadingRoster(false)
    }

    return () => { cancelled = true }
  }, [active, detail, currentState, courseCode, instanceId, prefilledById, theoryCtx.studentsGrades, examPackId])

  if (!active || !detail || detail.process_code !== PROCESS_CODE) {
    return null
  }

  const isTerminal = isTerminalState(currentState)
  const hint = STATE_HINTS[currentState]
    || 'خاتمه دروس تئوری — طبق راهنمای مرحله اقدام کنید.'
  const studentRows = roster.filter((r) => (r.role || 'student') !== 'teaching_assistant')

  const findTransition = (event) => availableTransitions.find((t) => t.trigger_event === event)

  const updateRow = (studentId, patch) => {
    setRoster((prev) => prev.map((r) => {
      if (r.student_id !== studentId) return r
      const next = { ...r, ...patch }
      const attendance = next.attendance_score ?? computeAttendanceScore(next.absence_count)
      const total = computeTotalScore(next.participation_score, next.test_score, attendance)
      return {
        ...next,
        attendance_score: attendance,
        total_score: total,
        pass_fail: labelPassFail(total),
        borderline: labelBorderlineStatus(total),
      }
    }))
  }

  const handleSession18Submit = async () => {
    const tr = findTransition('session_18_submitted')
    if (!tr || !instanceId) {
      showToast?.('اقدام ثبت جلسه ۱۸ در دسترس نیست.', 'error')
      return
    }
    const packCheck = validateExamPackId(examPackId)
    if (!packCheck.ok) {
      showToast?.(packCheck.message, 'error')
      return
    }
    for (const row of studentRows) {
      const pCheck = validateParticipation(row.participation_score)
      if (!pCheck.ok) {
        showToast?.(`${row.student_name}: ${pCheck.message}`, 'error')
        return
      }
    }
    setSubmitting(true)
    try {
      const payload = buildSession18Payload(
        roster,
        courseCode,
        theoryCtx.courseName,
        examPackId,
      )
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: tr.trigger_event,
        payload,
        ...(tr.to_state ? { to_state: tr.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('مشارکت و پک آزمون ثبت شد — آزمون برای دانشجویان باز شد')
        onRefreshInstance?.()
      } else {
        showToast?.(res.data?.error || 'خطا در ثبت', 'error')
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'خطا در ثبت'
      showToast?.(typeof msg === 'string' ? msg : 'خطا در ثبت', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="card"
      data-testid="theory-course-completion-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelTheoryState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TheoryFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="نام درس" value={theoryCtx.courseName} tone="#7c3aed" bg="#f5f3ff" />
          <InfoTile label="بارم" value={scoringSummaryLabel()} tone="#7c3aed" bg="#ede9fe" />
          {theoryCtx.examPackId && (
            <InfoTile label="پک آزمون" value={theoryCtx.examPackId} tone="#0d9488" bg="#f0fdfa" />
          )}
          {theoryCtx.courseHasTa && theoryCtx.taPassFail && (
            <InfoTile label="وضعیت TA" value={theoryCtx.taPassFail} tone="#d97706" bg="#fffbeb" />
          )}
        </div>

        {!isTerminal && (
          <TheorySlaBanner ctx={ctx} startedAt={detail.started_at} currentState={currentState} />
        )}

        {hint && (
          <TheoryHintBlock tone={currentState?.includes('delay') ? 'danger' : 'info'}>
            {hint}
          </TheoryHintBlock>
        )}

        {currentState === 'session_18_entry' && (
          <>
            <div style={{ marginBottom: '0.75rem' }}>
              <label className="form-label" style={{ fontSize: '0.85rem' }}>
                پک سوالات آزمون نهایی (
                {EXAM_MAX.toLocaleString('fa-IR')}
                {' '}
                نمره)
              </label>
              <input
                type="text"
                className="form-input"
                value={examPackId}
                onChange={(e) => setExamPackId(e.target.value)}
                placeholder="شناسه پک از بانک سوالات LMS"
                data-testid="theory-exam-pack-id"
              />
            </div>

            {loadingRoster ? (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>در حال بارگذاری لیست کلاس…</p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '0.75rem' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>نام</th>
                      <th>حضور (خودکار)</th>
                      <th>
                        مشارکت (۰–
                        {PARTICIPATION_MAX.toLocaleString('fa-IR')}
                        )
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{row.student_name || '—'}</td>
                        <td>{labelGrade(row.attendance_score)}</td>
                        <td>
                          <input
                            type="number"
                            className="form-input"
                            min={0}
                            max={PARTICIPATION_MAX}
                            value={row.participation_score}
                            onChange={(e) => updateRow(row.student_id, { participation_score: e.target.value })}
                            style={{ width: '4.5rem' }}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <button
              type="button"
              className="btn btn-primary btn-sm"
              data-testid="theory-session-18-submit"
              disabled={submitting || !findTransition('session_18_submitted') || loadingRoster}
              onClick={handleSession18Submit}
            >
              {submitting ? 'در حال ثبت…' : 'ثبت مشارکت و تأیید برگزاری آزمون'}
            </button>
          </>
        )}

        {['final_exam_open', 'grades_computed', 'borderline_student_choice', 'retake_exam_open'].includes(currentState) && studentRows.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: '0.5rem' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
              <thead>
                <tr>
                  <th>نام</th>
                  <th>مشارکت</th>
                  <th>حضور</th>
                  <th>آزمون</th>
                  <th>جمع</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {studentRows.map((row, idx) => (
                  <tr key={row.student_id || idx}>
                    <td>{row.student_name || '—'}</td>
                    <td>{labelGrade(row.participation_score)}</td>
                    <td>{labelGrade(row.attendance_score)}</td>
                    <td>{labelGrade(row.test_score)}</td>
                    <td>{row.total_score != null ? row.total_score.toLocaleString('fa-IR') : '—'}</td>
                    <td>{row.pass_fail || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {currentState === 'qualitative_eval_pending' && (
          <>
            <TheoryHintBlock title="ارزیابی کیفی" tone="info">
              فرم ارزیابی کیفی (سوال ۷ و ۸) را ظرف ۴ روز پس از جلسه ۱۸ برای تک‌تک دانشجویان در فرم پایین صفحه تکمیل کنید.
            </TheoryHintBlock>
            {studentRows.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>نام</th>
                      <th>جمع</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{row.student_name || '—'}</td>
                        <td>{row.total_score != null ? row.total_score.toLocaleString('fa-IR') : '—'}</td>
                        <td>{row.pass_fail || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {isTerminal && studentRows.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: '0.5rem' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
              <thead>
                <tr>
                  <th>نام</th>
                  <th>جمع</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {studentRows.map((row, idx) => (
                  <tr key={row.student_id || idx}>
                    <td>{row.student_name || '—'}</td>
                    <td>{row.total_score != null ? row.total_score.toLocaleString('fa-IR') : '—'}</td>
                    <td>{row.pass_fail || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
