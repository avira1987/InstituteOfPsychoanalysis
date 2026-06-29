import React, { useEffect, useMemo, useState } from 'react'
import { panelApi, processExecApi } from '../services/api'
import {
  buildStudentsGradesPayload,
  isTerminalState,
  labelParticipationGrade,
  labelTaAttendanceState,
  labelTaPassFail,
  PROCESS_CODE,
  PROCESS_TITLE_FA,
  resolveLessonCompletionContext,
  rosterRowToGradeRow,
  STATE_HINTS,
  TA_PASS_THRESHOLD,
  TaAttendanceFlowStepper,
  TaAttendanceHintBlock,
  TaAttendanceSlaBanner,
  InfoTile,
  validateParticipationScore,
} from '../utils/filmObservationTaAttendanceDisplay'

/**
 * داشبورد مدرس — خاتمه درس عملی کاربردی / مشاهده فیلم (بخش TA و حضور/مشارکت) — فرایند SOP ۷۵.
 */
export default function FilmObservationTaAttendancePanel({
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
  const lessonCtx = useMemo(() => resolveLessonCompletionContext(ctx), [ctx])
  const courseCode = lessonCtx.courseCode

  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const submitTransition = availableTransitions.find(
    (t) => t.trigger_event === 'grades_submitted',
  )

  const prefilledById = useMemo(() => {
    const map = {}
    ;(lessonCtx.studentsGrades || []).forEach((row) => {
      if (row?.student_id) map[String(row.student_id)] = row
    })
    return map
  }, [lessonCtx.studentsGrades])

  useEffect(() => {
    if (!active || !detail || detail.process_code !== PROCESS_CODE) return
    if (currentState !== 'grades_entry') return

    let cancelled = false
    setLoadingRoster(true)

    const applyRows = (rows) => {
      if (cancelled) return
      setRoster(rows.map((r) => rosterRowToGradeRow(r, prefilledById)))
    }

    if (courseCode) {
      panelApi.instructorCourseRoster(courseCode)
        .then((res) => {
          const apiRows = res.data?.roster || []
          if (apiRows.length) {
            applyRows(apiRows)
          } else if (lessonCtx.studentsGrades.length) {
            applyRows(lessonCtx.studentsGrades.map((g) => ({
              student_id: g.student_id,
              name_fa: g.student_name,
              role: 'student',
              absence_count: g.absence_count,
              participation_score: g.participation_score ?? g.grade,
            })))
          } else {
            applyRows([])
          }
        })
        .catch((e) => {
          if (cancelled) return
          const msg = e?.response?.data?.detail || e.message || 'خطا در بارگذاری لیست کلاس'
          showToast?.(typeof msg === 'string' ? msg : 'خطا در بارگذاری لیست کلاس', 'error')
          if (lessonCtx.studentsGrades.length) {
            applyRows(lessonCtx.studentsGrades.map((g) => ({
              student_id: g.student_id,
              name_fa: g.student_name,
              role: 'student',
            })))
          } else {
            setRoster([])
          }
        })
        .finally(() => {
          if (!cancelled) setLoadingRoster(false)
        })
    } else if (lessonCtx.studentsGrades.length) {
      applyRows(lessonCtx.studentsGrades.map((g) => ({
        student_id: g.student_id,
        name_fa: g.student_name,
        role: 'student',
        absence_count: g.absence_count,
        participation_score: g.participation_score ?? g.grade,
      })))
      setLoadingRoster(false)
    } else {
      setRoster([])
      setLoadingRoster(false)
    }

    return () => { cancelled = true }
  }, [
    active,
    detail,
    currentState,
    courseCode,
    lessonCtx.studentsGrades,
    prefilledById,
    showToast,
  ])

  if (!active || !detail || detail.process_code !== PROCESS_CODE) {
    return null
  }

  const isTerminal = isTerminalState(currentState)
  const hint = STATE_HINTS[currentState]
    || 'خاتمه درس عملی کاربردی / مشاهده فیلم — طبق راهنمای مرحله و فرم پایین اقدام کنید.'
  const sessionLabel = lessonCtx.sessionIndex != null
    ? lessonCtx.sessionIndex.toLocaleString('fa-IR')
    : '۱۸'
  const taRow = roster.find((r) => r.role === 'teaching_assistant')
  const studentRows = roster.filter((r) => (r.role || 'student') !== 'teaching_assistant')

  const setParticipation = (studentId, raw) => {
    setRoster((prev) => prev.map((r) => (
      r.student_id === studentId ? { ...r, participation_score: raw } : r
    )))
  }

  const handleSubmit = async () => {
    if (!submitTransition || !instanceId) {
      showToast?.('اقدام ثبت نمرات در دسترس نیست.', 'error')
      return
    }
    if (!studentRows.length) {
      showToast?.('لیست دانشجویان خالی است.', 'error')
      return
    }
    for (const row of studentRows) {
      const check = validateParticipationScore(row.participation_score)
      if (!check.ok) {
        showToast?.(`${row.student_name}: ${check.message}`, 'error')
        return
      }
    }

    setSubmitting(true)
    try {
      const students_grades = buildStudentsGradesPayload(roster)
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: submitTransition.trigger_event,
        payload: {
          course_name: lessonCtx.courseName || courseCode,
          course_code: courseCode,
          session_index: lessonCtx.sessionIndex,
          students_grades,
        },
        ...(submitTransition.to_state ? { to_state: submitTransition.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('نمرات مشارکت ثبت و قفل شد')
        onRefreshInstance?.()
      } else {
        showToast?.(res.data?.error || 'خطا در ثبت نمرات', 'error')
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'خطا در ثبت نمرات'
      showToast?.(typeof msg === 'string' ? msg : 'خطا در ثبت نمرات', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="card"
      data-testid="film-observation-ta-attendance-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelTaAttendanceState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaAttendanceFlowStepper currentState={currentState} compact={compact} />

        <div
          data-testid="film-observation-ta-summary"
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="نام درس" value={lessonCtx.courseName} tone="#0d9488" bg="#f0fdfa" />
          <InfoTile label="جلسه" value={sessionLabel} tone="#0d9488" bg="#f0fdfa" />
          {lessonCtx.teachingAssistantName && (
            <InfoTile
              label="کمک‌مدرس"
              value={lessonCtx.teachingAssistantName}
              tone="#7c3aed"
              bg="#f5f3ff"
            />
          )}
          {lessonCtx.attendanceScore != null && (
            <InfoTile
              label="نمره حضور (سیستمی، سقف ۸)"
              value={lessonCtx.attendanceScore.toLocaleString('fa-IR')}
              tone="#2563eb"
              bg="#eff6ff"
            />
          )}
          {lessonCtx.taTotalScore != null && (
            <InfoTile
              label={`نمره TA (آستانه ${TA_PASS_THRESHOLD.toLocaleString('fa-IR')})`}
              value={`${lessonCtx.taTotalScore.toLocaleString('fa-IR')} — ${lessonCtx.taPassFail || labelTaPassFail(lessonCtx.taTotalScore)}`}
              tone={lessonCtx.taTotalScore >= TA_PASS_THRESHOLD ? '#059669' : '#dc2626'}
              bg={lessonCtx.taTotalScore >= TA_PASS_THRESHOLD ? '#ecfdf5' : '#fef2f2'}
            />
          )}
        </div>

        {!isTerminal && (
          <TaAttendanceSlaBanner ctx={ctx} startedAt={detail.started_at} />
        )}

        {currentState === 'grades_entry' && !courseCode && !studentRows.length && (
          <TaAttendanceHintBlock title="کد درس" tone="warn">
            کد درس در زمینهٔ پرونده ثبت نشده است. از فرم پایین یا پشتیبانی، فیلد course_code را تنظیم کنید.
          </TaAttendanceHintBlock>
        )}

        <TaAttendanceHintBlock tone="info">
          نمره مشارکت (۰–۱۰) را در روز جلسه ۱۸ ثبت کنید. نمره حضور: حداکثر ۸ (کسر ۲ به ازای هر غیبت).
          گزارش PDF پایانی در فرایند «خاتمه هر درس عملی کاربردی و مشاهده فیلم‌ها» (فرایند ۶۴) است.
          وظایف TA این رسته: مشورت آموزشی، آپلود جستار و دقایق فیلم، ثبت وبلاگ.
        </TaAttendanceHintBlock>

        {hint && (
          <TaAttendanceHintBlock tone={currentState === 'delay_reported' ? 'danger' : 'info'}>
            {hint}
          </TaAttendanceHintBlock>
        )}

        {currentState === 'grades_entry' && (
          <>
            {loadingRoster ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری لیست کلاس…</p>
            ) : studentRows.length === 0 ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>
                هنوز دانشجویی در این درس ثبت‌نام نکرده است.
              </p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '0.85rem' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>ردیف</th>
                      <th>نام</th>
                      <th>غیبت ترم</th>
                      <th>نمره حضور</th>
                      <th>مشارکت (۰–۱۰)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{(idx + 1).toLocaleString('fa-IR')}</td>
                        <td>{row.student_name || '—'}</td>
                        <td>{(row.absence_count ?? 0).toLocaleString('fa-IR')}</td>
                        <td>{(row.attendance_score ?? 8).toLocaleString('fa-IR')}</td>
                        <td>
                          <input
                            type="number"
                            className="form-input"
                            min={0}
                            max={10}
                            step={0.5}
                            value={row.participation_score ?? ''}
                            onChange={(e) => setParticipation(row.student_id, e.target.value)}
                            data-testid={`participation-${row.student_id}`}
                            style={{ width: '5rem' }}
                            aria-label={`نمره مشارکت — ${row.student_name}`}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {taRow && (
              <div
                data-testid="film-observation-ta-row-summary"
                style={{
                  marginBottom: '0.85rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  background: '#f5f3ff',
                  borderRight: '4px solid #7c3aed',
                  fontSize: '0.86rem',
                }}
              >
                <strong>کمک‌مدرس: </strong>
                {taRow.student_name || lessonCtx.teachingAssistantName || '—'}
                {lessonCtx.taTotalScore != null && (
                  <>
                    {' — '}
                    نمره TA:
                    {' '}
                    {lessonCtx.taTotalScore.toLocaleString('fa-IR')}
                    {' '}
                    (
                    {lessonCtx.taPassFail || labelTaPassFail(lessonCtx.taTotalScore)}
                    )
                  </>
                )}
              </div>
            )}

            {studentRows.length > 0 && (
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '0.75rem' }}>
                پیش‌نمایش مشارکت:
                {' '}
                {studentRows.map((r) => `${r.student_name}: ${labelParticipationGrade(r.participation_score)}`).join(' · ')}
              </div>
            )}

            <button
              type="button"
              className="btn btn-primary btn-sm"
              data-testid="film-observation-ta-submit-grades"
              disabled={submitting || !submitTransition || studentRows.length === 0}
              onClick={handleSubmit}
            >
              {submitting ? 'در حال ثبت…' : 'ثبت نمرات مشارکت و قفل'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
