import React, { useEffect, useMemo, useState } from 'react'
import { panelApi, processExecApi } from '../services/api'
import {
  PROCESS_CODE,
  PROCESS_TITLE_FA,
  STATE_HINTS,
  HOURS_PER_PASS_DISPLAY,
  GroupSupervisionFlowStepper,
  GroupSupervisionHintBlock,
  GroupSupervisionSlaBanner,
  InfoTile,
  buildPassFailPayload,
  buildTaGradesPayload,
  computeAttendanceScore,
  computeTaTotal,
  hoursSummaryLabel,
  isTerminalState,
  labelGroupSupervisionState,
  labelPassFail,
  labelTaPassFail,
  resolveGroupSupervisionContext,
  rosterRowToPassFailRow,
  validatePassFailRow,
} from '../utils/groupSupervisionCourseCompletionDisplay'

/**
 * داشبورد مدرس — خاتمه هر درس سوپرویژن گروهی — فرایند SOP ۶۲.
 */
export default function GroupSupervisionCourseCompletionPanel({
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
  const gsCtx = useMemo(() => resolveGroupSupervisionContext(ctx), [ctx])
  const courseCode = gsCtx.courseCode

  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [taAttendance, setTaAttendance] = useState(ctx.ta_attendance_score ?? '')
  const [taDuties, setTaDuties] = useState(ctx.ta_duties_score ?? '')

  const prefilledById = useMemo(() => {
    const map = {}
    ;(gsCtx.studentsGrades || []).forEach((row) => {
      if (row?.student_id) map[String(row.student_id)] = row
    })
    return map
  }, [gsCtx.studentsGrades])

  useEffect(() => {
    if (!active || !detail || detail.process_code !== PROCESS_CODE) return
    if (!courseCode) return
    if (!['session_18_pass_fail_entry', 'pass_fail_applied', 'ta_evaluation_entry', 'qualitative_eval_pending', 'grades_locked'].includes(currentState)) {
      return
    }

    let cancelled = false
    setLoadingRoster(true)

    panelApi.groupSupervisionGradesPreview(courseCode, instanceId)
      .then((res) => {
        if (cancelled) return
        const data = res.data || {}
        const apiRows = data.students_grades || []
        setRoster(apiRows.map((r) => rosterRowToPassFailRow(r, prefilledById)))
        if (data.ta_attendance_suggested != null && taAttendance === '') {
          setTaAttendance(String(data.ta_attendance_suggested))
        }
      })
      .catch(() => {
        if (cancelled) return
        panelApi.instructorCourseRoster(courseCode)
          .then((res) => {
            if (cancelled) return
            const rows = res.data?.roster || []
            setRoster(rows
              .filter((r) => (r.role || 'student') !== 'teaching_assistant')
              .map((r) => rosterRowToPassFailRow(r, prefilledById)))
          })
          .catch(() => { if (!cancelled) setRoster([]) })
      })
      .finally(() => { if (!cancelled) setLoadingRoster(false) })

    return () => { cancelled = true }
  }, [active, detail, currentState, courseCode, instanceId, prefilledById, taAttendance])

  if (!active || !detail || detail.process_code !== PROCESS_CODE) {
    return null
  }

  const isTerminal = isTerminalState(currentState)
  const hint = STATE_HINTS[currentState]
    || 'خاتمه درس سوپرویژن گروهی — طبق راهنمای مرحله اقدام کنید.'
  const studentRows = roster.filter((r) => (r.role || 'student') !== 'teaching_assistant')
  const taRow = roster.find((r) => (r.role || '') === 'teaching_assistant')

  const findTransition = (event) => availableTransitions.find((t) => t.trigger_event === event)

  const updateRow = (studentId, patch) => {
    setRoster((prev) => prev.map((r) => {
      if (r.student_id !== studentId) return r
      const next = { ...r, ...patch }
      if (patch.pass_fail != null) {
        const pf = String(patch.pass_fail).toUpperCase()
        const hoursBefore = Number(next.group_supervision_hours_before) || 0
        const hoursAdded = pf === 'PASS' ? 33.3333 : 0
        return {
          ...next,
          pass_fail: pf,
          hours_added: hoursAdded,
          hours_after: Math.min(100, hoursBefore + hoursAdded),
        }
      }
      return next
    }))
  }

  const handlePassFailSubmit = async () => {
    const tr = findTransition('pass_fail_submitted')
    if (!tr || !instanceId) {
      showToast?.('اقدام ثبت Pass/Fail در دسترس نیست.', 'error')
      return
    }
    for (const row of studentRows) {
      const check = validatePassFailRow(row)
      if (!check.ok) {
        showToast?.(`${row.student_name}: ${check.message}`, 'error')
        return
      }
    }
    setSubmitting(true)
    try {
      const payload = buildPassFailPayload(roster, courseCode, gsCtx.courseName)
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: tr.trigger_event,
        payload,
        ...(tr.to_state ? { to_state: tr.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('وضعیت Pass/Fail ثبت شد')
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

  const handleTaSubmit = async () => {
    const tr = findTransition('ta_grades_submitted')
    if (!tr || !instanceId) {
      showToast?.('اقدام ثبت TA در دسترس نیست.', 'error')
      return
    }
    if (taAttendance === '' || taDuties === '') {
      showToast?.('نمره حضور و وظایف TA الزامی است.', 'error')
      return
    }
    setSubmitting(true)
    try {
      const payload = buildTaGradesPayload(
        taAttendance,
        taDuties,
        courseCode,
        gsCtx.courseName,
        taRow?.student_name || gsCtx.taName,
      )
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: tr.trigger_event,
        payload,
        ...(tr.to_state ? { to_state: tr.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('نمره TA ثبت شد')
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

  const taTotalPreview = computeTaTotal(taAttendance, taDuties)

  return (
    <div
      className="card"
      data-testid="group-supervision-course-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem', border: '2px solid #0d9488' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelGroupSupervisionState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <GroupSupervisionFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.75rem',
          }}
        >
          <InfoTile label="درس" value={gsCtx.courseName} tone="#0d9488" bg="#f0fdfa" />
          <InfoTile label="ساعات هر Pass" value={`+${HOURS_PER_PASS_DISPLAY}`} tone="#7c3aed" bg="#f5f3ff" />
        </div>

        <GroupSupervisionSlaBanner ctx={ctx} currentState={currentState} startedAt={detail.started_at} />
        <GroupSupervisionHintBlock tone={currentState === 'session_18_pass_fail_entry' ? 'warn' : 'info'}>
          {hint}
        </GroupSupervisionHintBlock>
        <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0.5rem 0 0.75rem' }}>
          {hoursSummaryLabel()}
        </p>

        {currentState === 'session_18_pass_fail_entry' && (
          <>
            {loadingRoster ? (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>در حال بارگذاری لیست کلاس…</p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '0.75rem' }} data-testid="group-supervision-pass-fail-table">
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>نام دانشجو</th>
                      <th>ساعات فعلی</th>
                      <th>Pass/Fail</th>
                      <th>پس از ثبت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{row.student_name || '—'}</td>
                        <td>{Number(row.group_supervision_hours_before || 0).toLocaleString('fa-IR', { maximumFractionDigits: 1 })}</td>
                        <td>
                          <select
                            className="form-input"
                            value={row.pass_fail || 'PASS'}
                            onChange={(e) => updateRow(row.student_id, { pass_fail: e.target.value })}
                            style={{ minWidth: '6rem' }}
                          >
                            <option value="PASS">PASS</option>
                            <option value="FAIL">FAIL</option>
                          </select>
                        </td>
                        <td>
                          {row.pass_fail === 'PASS'
                            ? `+${HOURS_PER_PASS_DISPLAY} → ${Number(row.hours_after || 0).toLocaleString('fa-IR', { maximumFractionDigits: 1 })}`
                            : 'بدون افزایش'}
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
              data-testid="group-supervision-pass-fail-submit"
              disabled={submitting || !findTransition('pass_fail_submitted') || loadingRoster}
              onClick={handlePassFailSubmit}
            >
              {submitting ? 'در حال ثبت…' : 'ثبت نهایی Pass/Fail'}
            </button>
          </>
        )}

        {(currentState === 'pass_fail_applied' || isTerminal) && studentRows.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: '0.5rem' }} data-testid="group-supervision-summary-table">
            <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
              <thead>
                <tr>
                  <th>نام</th>
                  <th>وضعیت</th>
                  <th>ساعات اضافه</th>
                </tr>
              </thead>
              <tbody>
                {(isTerminal ? (gsCtx.studentsGrades.length ? gsCtx.studentsGrades : studentRows) : studentRows).map((row, idx) => (
                  <tr key={row.student_id || idx}>
                    <td>{row.student_name || '—'}</td>
                    <td>{labelPassFail(row.pass_fail)}</td>
                    <td>
                      {row.pass_fail === 'PASS' || row.pass_fail === 'pass'
                        ? `+${HOURS_PER_PASS_DISPLAY}`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {currentState === 'ta_evaluation_entry' && (
          <div style={{ marginTop: '0.75rem' }} data-testid="group-supervision-ta-section">
            <p style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              نام TA:
              {' '}
              <strong>{taRow?.student_name || gsCtx.taName || '—'}</strong>
            </p>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
              <div>
                <label className="form-label" style={{ fontSize: '0.82rem' }}>نمره حضور (۰–۸)</label>
                <input
                  type="number"
                  className="form-input"
                  min={0}
                  max={8}
                  value={taAttendance}
                  onChange={(e) => setTaAttendance(e.target.value)}
                  style={{ width: '5rem' }}
                />
                <span style={{ fontSize: '0.75rem', color: '#64748b', marginRight: '0.35rem' }}>
                  پیشنهاد:
                  {' '}
                  {computeAttendanceScore(taRow?.absence_count ?? ctx.ta_absence_count ?? 0)}
                </span>
              </div>
              <div>
                <label className="form-label" style={{ fontSize: '0.82rem' }}>نمره وظایف</label>
                <input
                  type="number"
                  className="form-input"
                  min={0}
                  max={92}
                  value={taDuties}
                  onChange={(e) => setTaDuties(e.target.value)}
                  style={{ width: '5rem' }}
                />
              </div>
              <div>
                <label className="form-label" style={{ fontSize: '0.82rem' }}>جمع / وضعیت</label>
                <div style={{ fontWeight: 700, paddingTop: '0.35rem' }}>
                  {taTotalPreview != null ? taTotalPreview.toLocaleString('fa-IR') : '—'}
                  {' '}
                  —
                  {' '}
                  {labelTaPassFail(taTotalPreview)}
                </div>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              data-testid="group-supervision-ta-submit"
              disabled={submitting || !findTransition('ta_grades_submitted')}
              onClick={handleTaSubmit}
            >
              {submitting ? 'در حال ثبت…' : 'ثبت نمره TA'}
            </button>
          </div>
        )}

        {currentState === 'qualitative_eval_pending' && (
          <>
            <GroupSupervisionHintBlock title="ارزیابی کیفی" tone="info">
              فرم ارزیابی کیفی (سوال ۷ و ۸) را ظرف ۴ روز پس از جلسه ۱۸ برای تک‌تک دانشجویان در فرم پایین صفحه تکمیل کنید.
            </GroupSupervisionHintBlock>
            {studentRows.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>نام</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{row.student_name || '—'}</td>
                        <td>{labelPassFail(row.pass_fail)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
