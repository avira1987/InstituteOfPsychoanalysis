import React, { useEffect, useMemo, useState } from 'react'
import { panelApi, processExecApi } from '../services/api'
import {
  ATTENDANCE_MAX,
  BORDERLINE_SMS_FA,
  PARTICIPATION_MAX,
  PROCESS_CODE,
  PROCESS_TITLE_FA,
  REPORT_MAX,
  STATE_HINTS,
  buildStudentsGradesPayload,
  FilmCompletionFlowStepper,
  FilmCompletionHintBlock,
  FilmCompletionSlaBanner,
  InfoTile,
  ReportPdfLink,
  isTerminalState,
  computeTotalScore,
  labelBorderlineStatus,
  labelFilmCompletionState,
  labelPassFail,
  labelReportGrade,
  resolveFilmCompletionContext,
  rosterRowToReportGradeRow,
  validateReportGrade,
} from '../utils/filmObservationCourseCompletionDisplay'

/**
 * داشبورد مدرس — خاتمه درس عملی کاربردی / مشاهده فیلم (گزارش PDF و نمره نهایی) — فرایند SOP ۶۴.
 */
export default function FilmObservationCourseCompletionPanel({
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
  const filmCtx = useMemo(() => resolveFilmCompletionContext(ctx), [ctx])
  const courseCode = filmCtx.courseCode

  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const submitTransition = availableTransitions.find(
    (t) => t.trigger_event === 'grades_submitted',
  )

  const prefilledById = useMemo(() => {
    const map = {}
    ;(filmCtx.studentsGrades || []).forEach((row) => {
      if (row?.student_id) map[String(row.student_id)] = row
    })
    return map
  }, [filmCtx.studentsGrades])

  const ctxDefaults = useMemo(() => ({
    participationScore: filmCtx.participationScore,
    attendanceScore: filmCtx.attendanceScore,
  }), [filmCtx.participationScore, filmCtx.attendanceScore])

  useEffect(() => {
    if (!active || !detail || detail.process_code !== PROCESS_CODE) return
    if (currentState !== 'grades_entry') return

    let cancelled = false
    setLoadingRoster(true)

    const applyRows = (rows) => {
      if (cancelled) return
      setRoster(rows.map((r) => rosterRowToReportGradeRow(r, prefilledById, ctxDefaults)))
    }

    if (courseCode) {
      panelApi.instructorCourseRoster(courseCode, { enrichFilmReports: true })
        .then((res) => {
          const apiRows = res.data?.roster || []
          if (apiRows.length) {
            applyRows(apiRows)
          } else if (filmCtx.studentsGrades.length) {
            applyRows(filmCtx.studentsGrades.map((g) => ({
              student_id: g.student_id,
              name_fa: g.student_name,
              role: 'student',
              participation_score: g.participation_score,
              attendance_score: g.attendance_score,
              report_grade: g.report_grade ?? g.grade,
              final_report_pdf: g.final_report_pdf ?? g.report_file,
            })))
          } else {
            applyRows([])
          }
        })
        .catch((e) => {
          if (cancelled) return
          const msg = e?.response?.data?.detail || e.message || 'خطا در بارگذاری لیست کلاس'
          showToast?.(typeof msg === 'string' ? msg : 'خطا در بارگذاری لیست کلاس', 'error')
          if (filmCtx.studentsGrades.length) {
            applyRows(filmCtx.studentsGrades.map((g) => ({
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
    } else if (filmCtx.studentsGrades.length) {
      applyRows(filmCtx.studentsGrades.map((g) => ({
        student_id: g.student_id,
        name_fa: g.student_name,
        role: 'student',
        participation_score: g.participation_score,
        attendance_score: g.attendance_score,
        report_grade: g.report_grade ?? g.grade,
        final_report_pdf: g.final_report_pdf ?? g.report_file,
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
    filmCtx.studentsGrades,
    prefilledById,
    ctxDefaults,
    showToast,
  ])

  if (!active || !detail || detail.process_code !== PROCESS_CODE) {
    return null
  }

  const isTerminal = isTerminalState(currentState)
  const hint = STATE_HINTS[currentState]
    || 'خاتمه درس عملی کاربردی / مشاهده فیلم — طبق راهنمای مرحله و فرم پایین اقدام کنید.'
  const studentRows = roster.filter((r) => (r.role || 'student') !== 'teaching_assistant')

  const setReportGrade = (studentId, raw) => {
    setRoster((prev) => prev.map((r) => {
      if (r.student_id !== studentId) return r
      const participation = Number(r.participation_score) || 0
      const attendance = Number(r.attendance_score) || 0
      const report = raw === '' ? '' : Number(raw)
      const total = raw === '' ? null : computeTotalScore(participation, attendance, report)
      return {
        ...r,
        report_grade: raw,
        total_score: total,
        pass_fail: total != null ? labelPassFail(total) : null,
        borderline: total != null ? labelBorderlineStatus(total) : null,
      }
    }))
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
      const check = validateReportGrade(row.report_grade)
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
          course_name: filmCtx.courseName || courseCode,
          course_code: courseCode,
          session_index: filmCtx.sessionIndex,
          students_grades,
        },
        ...(submitTransition.to_state ? { to_state: submitTransition.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('نمرات گزارش ثبت و قفل شد')
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
      data-testid="film-observation-course-completion-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelFilmCompletionState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <FilmCompletionFlowStepper currentState={currentState} compact={compact} />

        <div
          data-testid="film-observation-course-summary"
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="نام درس" value={filmCtx.courseName} tone="#7c3aed" bg="#f5f3ff" />
          <InfoTile
            label="بارم"
            value={`مشارکت ${PARTICIPATION_MAX.toLocaleString('fa-IR')} + حضور ${ATTENDANCE_MAX.toLocaleString('fa-IR')} + گزارش ${REPORT_MAX.toLocaleString('fa-IR')}`}
            tone="#0d9488"
            bg="#f0fdfa"
          />
        </div>

        {!isTerminal && (
          <FilmCompletionSlaBanner ctx={ctx} startedAt={detail.started_at} />
        )}

        {currentState === 'grades_entry' && !courseCode && !studentRows.length && (
          <FilmCompletionHintBlock title="کد درس" tone="warn">
            کد درس در زمینهٔ پرونده ثبت نشده است. از فرم پایین یا پشتیبانی، فیلد course_code را تنظیم کنید.
          </FilmCompletionHintBlock>
        )}

        <FilmCompletionHintBlock tone="info">
          نمرات مشارکت و حضور از فرایند ۷۵ (`film_observation_ta_attendance_completion`) می‌آید.
          گزارش PDF از پایان جلسه ۱۷ تا ۲۴:۰۰ جلسه ۱۸ قابل آپلود است. مهلت تصحیح اولیه: ۵ روز.
        </FilmCompletionHintBlock>

        {hint && (
          <FilmCompletionHintBlock tone={currentState === 'delay_reported' ? 'danger' : 'info'}>
            {hint}
          </FilmCompletionHintBlock>
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
                      <th>گزارش PDF</th>
                      <th>مشارکت</th>
                      <th>حضور</th>
                      <th>گزارش (۰–۸۲)</th>
                      <th>جمع</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{(idx + 1).toLocaleString('fa-IR')}</td>
                        <td>{row.student_name || '—'}</td>
                        <td>
                          <ReportPdfLink fileValue={row.report_file} />
                        </td>
                        <td>{labelReportGrade(row.participation_score)}</td>
                        <td>{labelReportGrade(row.attendance_score)}</td>
                        <td>
                          <input
                            type="number"
                            className="form-input"
                            min={0}
                            max={REPORT_MAX}
                            step={0.5}
                            value={row.report_grade ?? ''}
                            onChange={(e) => setReportGrade(row.student_id, e.target.value)}
                            data-testid={`report-grade-${row.student_id}`}
                            style={{ width: '5rem' }}
                            aria-label={`نمره گزارش — ${row.student_name}`}
                          />
                        </td>
                        <td>
                          {row.total_score != null
                            ? row.total_score.toLocaleString('fa-IR')
                            : '—'}
                        </td>
                        <td>
                          {row.pass_fail || '—'}
                          {row.borderline && (
                            <span style={{ display: 'block', fontSize: '0.75rem', color: '#d97706' }}>
                              مرزی
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {studentRows.some((r) => r.borderline) && (
              <FilmCompletionHintBlock title="نمره مرزی (۶۴–۷۳)" tone="warn">
                {BORDERLINE_SMS_FA}
              </FilmCompletionHintBlock>
            )}

            <FilmCompletionHintBlock title="ارزیابی کیفی" tone="info">
              فرم ارزیابی کیفی (سوال ۷ و ۸) را ظرف ۴ روز پس از جلسه ۱۸ برای تک‌تک دانشجویان تکمیل کنید (فرم پایین صفحه).
            </FilmCompletionHintBlock>

            {studentRows.length > 0 && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="film-observation-course-submit-grades"
                disabled={submitting || !submitTransition || studentRows.length === 0}
                onClick={handleSubmit}
                style={{ marginTop: '0.5rem' }}
              >
                {submitting ? 'در حال ثبت…' : 'ثبت نمرات گزارش و قفل'}
              </button>
            )}
          </>
        )}

        {isTerminal && studentRows.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: '0.5rem' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
              <thead>
                <tr>
                  <th>نام</th>
                  <th>گزارش</th>
                  <th>جمع</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {studentRows.map((row, idx) => (
                  <tr key={row.student_id || idx}>
                    <td>{row.student_name || '—'}</td>
                    <td>{labelReportGrade(row.report_grade)}</td>
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
