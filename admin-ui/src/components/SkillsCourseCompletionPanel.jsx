import React, { useEffect, useMemo, useState } from 'react'
import { panelApi, processExecApi } from '../services/api'
import {
  PROCESS_CODE,
  PROCESS_TITLE_FA,
  PRACTICAL_REFERENCE_HINT,
  STATE_HINTS,
  SkillsFlowStepper,
  SkillsHintBlock,
  SkillsSlaBanner,
  InfoTile,
  buildSession17Payload,
  buildSession18Payload,
  buildTaGradesPayload,
  computeAttendanceScore,
  computeTotalScore,
  isTerminalState,
  labelGrade,
  labelPassFail,
  labelSkillsState,
  resolveSkillsCompletionContext,
  rosterRowToSession17Row,
  rosterRowToSession18Row,
  scoringSummaryLabel,
  validateParticipation,
  validatePracticalGrade,
  validateTestGrade,
  variantLabel,
} from '../utils/skillsCourseCompletionDisplay'

/**
 * داشبورد مدرس — خاتمه دروس تکنیک: تمرین مهارت‌ها — فرایند SOP ۶۳.
 */
export default function SkillsCourseCompletionPanel({
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
  const skillsCtx = useMemo(() => resolveSkillsCompletionContext(ctx), [ctx])
  const courseCode = skillsCtx.courseCode
  const variant = skillsCtx.skillsVariant

  const [roster, setRoster] = useState([])
  const [loadingRoster, setLoadingRoster] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [testExamId, setTestExamId] = useState(ctx.test_exam_id || '')
  const [taAttendance, setTaAttendance] = useState(ctx.ta_attendance_score ?? '')
  const [taDuties, setTaDuties] = useState(ctx.ta_duties_score ?? '')

  const prefilledById = useMemo(() => {
    const map = {}
    ;(skillsCtx.studentsGrades || []).forEach((row) => {
      if (row?.student_id) map[String(row.student_id)] = row
    })
    return map
  }, [skillsCtx.studentsGrades])

  useEffect(() => {
    if (!active || !detail || detail.process_code !== PROCESS_CODE) return
    if (!courseCode) return

    let cancelled = false
    setLoadingRoster(true)

    panelApi.skillsCourseGradesPreview(courseCode, instanceId)
      .then((res) => {
        if (cancelled) return
        const data = res.data || {}
        const apiRows = data.students_grades || []
        if (currentState === 'session_17_grades_entry') {
          setRoster(apiRows.map((r) => rosterRowToSession17Row(r, prefilledById, data.skills_variant || variant)))
        } else {
          setRoster(apiRows.map((r) => rosterRowToSession18Row(r, prefilledById, data.skills_variant || variant)))
        }
        if (data.ta_name && !ctx.ta_name) {
          setTaAttendance((v) => v || '')
        }
      })
      .catch(() => {
        if (cancelled) return
        panelApi.instructorCourseRoster(courseCode)
          .then((res) => {
            if (cancelled) return
            const rows = res.data?.roster || []
            if (currentState === 'session_17_grades_entry') {
              setRoster(rows.map((r) => rosterRowToSession17Row(r, prefilledById, variant)))
            } else {
              setRoster(rows.map((r) => rosterRowToSession18Row(r, prefilledById, variant)))
            }
          })
          .catch(() => { if (!cancelled) setRoster([]) })
      })
      .finally(() => { if (!cancelled) setLoadingRoster(false) })

    return () => { cancelled = true }
  }, [active, detail, currentState, courseCode, instanceId, prefilledById, variant, ctx.ta_name])

  if (!active || !detail || detail.process_code !== PROCESS_CODE) {
    return null
  }

  const isTerminal = isTerminalState(currentState)
  const hint = STATE_HINTS[currentState]
    || 'خاتمه دروس تکنیک تمرین مهارت‌ها — طبق راهنمای مرحله اقدام کنید.'
  const studentRows = roster.filter((r) => (r.role || 'student') !== 'teaching_assistant')
  const taRow = roster.find((r) => (r.role || '') === 'teaching_assistant')

  const findTransition = (event) => availableTransitions.find((t) => t.trigger_event === event)

  const updateRow = (studentId, patch) => {
    setRoster((prev) => prev.map((r) => {
      if (r.student_id !== studentId) return r
      const next = { ...r, ...patch }
      if (currentState === 'session_18_grades_entry' || patch.test_score != null || patch.session_18_absent != null) {
        const attendance = computeAttendanceScore(next.absence_count)
        const incomplete = next.session_17_absent || next.session_18_absent
        const total = incomplete
          ? null
          : computeTotalScore(
            next.participation_score,
            next.practical_score,
            next.test_score,
            attendance,
          )
        return {
          ...next,
          attendance_score: attendance,
          incomplete,
          total_score: total,
          pass_fail: labelPassFail(total, incomplete),
        }
      }
      return next
    }))
  }

  const handleSession17Submit = async () => {
    const tr = findTransition('session_17_submitted')
    if (!tr || !instanceId) {
      showToast?.('اقدام ثبت جلسه ۱۷ در دسترس نیست.', 'error')
      return
    }
    for (const row of studentRows) {
      if (row.session_17_absent) continue
      const pCheck = validateParticipation(row.participation_score)
      if (!pCheck.ok) {
        showToast?.(`${row.student_name}: ${pCheck.message}`, 'error')
        return
      }
      const prCheck = validatePracticalGrade(row.practical_score, variant)
      if (!prCheck.ok) {
        showToast?.(`${row.student_name}: ${prCheck.message}`, 'error')
        return
      }
    }
    setSubmitting(true)
    try {
      const payload = buildSession17Payload(
        roster,
        courseCode,
        skillsCtx.courseName,
        variant,
      )
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: tr.trigger_event,
        payload,
        ...(tr.to_state ? { to_state: tr.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('نمرات جلسه ۱۷ ثبت شد')
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

  const handleSession18Submit = async () => {
    const tr = findTransition('session_18_submitted')
    if (!tr || !instanceId) {
      showToast?.('اقدام ثبت جلسه ۱۸ در دسترس نیست.', 'error')
      return
    }
    for (const row of studentRows) {
      if (row.session_18_absent || row.session_17_absent) continue
      const tCheck = validateTestGrade(row.test_score, variant)
      if (!tCheck.ok) {
        showToast?.(`${row.student_name}: ${tCheck.message}`, 'error')
        return
      }
    }
    setSubmitting(true)
    try {
      const payload = buildSession18Payload(roster, courseCode, skillsCtx.courseName, testExamId)
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: tr.trigger_event,
        payload,
        ...(tr.to_state ? { to_state: tr.to_state } : {}),
      })
      if (res.data?.success) {
        showToast?.('نمرات جلسه ۱۸ ثبت شد')
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
        skillsCtx.courseName,
        taRow?.student_name || skillsCtx.taName,
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
      showToast?.(e?.response?.data?.detail || e.message || 'خطا', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="card"
      data-testid="skills-course-completion-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelSkillsState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <SkillsFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="نام درس" value={skillsCtx.courseName} tone="#0d9488" bg="#f0fdfa" />
          <InfoTile label="نوع درس" value={variantLabel(variant)} tone="#7c3aed" bg="#f5f3ff" />
          <InfoTile label="بارم" value={scoringSummaryLabel(variant)} tone="#0d9488" bg="#ecfdf5" />
        </div>

        {!isTerminal && (
          <SkillsSlaBanner ctx={ctx} startedAt={detail.started_at} currentState={currentState} />
        )}

        {hint && (
          <SkillsHintBlock tone={currentState?.includes('delay') ? 'danger' : 'info'}>
            {hint}
          </SkillsHintBlock>
        )}

        {currentState === 'session_17_grades_entry' && (
          <SkillsHintBlock title="امتحان عملی" tone="warn">
            {PRACTICAL_REFERENCE_HINT}
            {' '}
            سقف عملی:
            {' '}
            {skillsCtx.practicalMax.toLocaleString('fa-IR')}
          </SkillsHintBlock>
        )}

        {currentState === 'session_17_grades_entry' && (
          <>
            {loadingRoster ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری لیست کلاس…</p>
            ) : studentRows.length === 0 ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>لیست دانشجویان خالی است.</p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '0.85rem' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>ردیف</th>
                      <th>نام</th>
                      <th>مشارکت (۰–۱۰)</th>
                      <th>عملی</th>
                      <th>غیبت جلسه ۱۷</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{(idx + 1).toLocaleString('fa-IR')}</td>
                        <td>{row.student_name || '—'}</td>
                        <td>
                          <input
                            type="number"
                            className="form-input"
                            min={0}
                            max={10}
                            step={0.5}
                            disabled={row.session_17_absent}
                            value={row.participation_score ?? ''}
                            onChange={(e) => updateRow(row.student_id, { participation_score: e.target.value })}
                            style={{ width: '4.5rem' }}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            className="form-input"
                            min={0}
                            max={skillsCtx.practicalMax}
                            step={0.5}
                            disabled={row.session_17_absent}
                            value={row.practical_score ?? ''}
                            onChange={(e) => updateRow(row.student_id, { practical_score: e.target.value })}
                            style={{ width: '4.5rem' }}
                          />
                        </td>
                        <td>
                          <input
                            type="checkbox"
                            checked={!!row.session_17_absent}
                            onChange={(e) => updateRow(row.student_id, { session_17_absent: e.target.checked })}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {studentRows.length > 0 && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="skills-session-17-submit"
                disabled={submitting || !findTransition('session_17_submitted')}
                onClick={handleSession17Submit}
              >
                {submitting ? 'در حال ثبت…' : 'ثبت نمرات جلسه ۱۷'}
              </button>
            )}
          </>
        )}

        {currentState === 'session_18_grades_entry' && (
          <>
            <div style={{ marginBottom: '0.75rem' }}>
              <label className="form-label" style={{ fontSize: '0.85rem' }}>شناسه آزمون بانک سوالات</label>
              <input
                type="text"
                className="form-input"
                value={testExamId}
                onChange={(e) => setTestExamId(e.target.value)}
                placeholder="اختیاری — شناسه آزمون تستی"
                style={{ maxWidth: '20rem' }}
              />
            </div>
            {loadingRoster ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری…</p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '0.85rem' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
                  <thead>
                    <tr>
                      <th>نام</th>
                      <th>مشارکت</th>
                      <th>عملی</th>
                      <th>تست (۰–{skillsCtx.testMax})</th>
                      <th>حضور</th>
                      <th>جمع</th>
                      <th>وضعیت</th>
                      <th>غیبت تست</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studentRows.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{row.student_name || '—'}</td>
                        <td>{labelGrade(row.participation_score)}</td>
                        <td>{labelGrade(row.practical_score)}</td>
                        <td>
                          <input
                            type="number"
                            className="form-input"
                            min={0}
                            max={skillsCtx.testMax}
                            step={0.5}
                            disabled={row.session_17_absent || row.session_18_absent}
                            value={row.test_score ?? ''}
                            onChange={(e) => updateRow(row.student_id, { test_score: e.target.value })}
                            style={{ width: '4.5rem' }}
                          />
                        </td>
                        <td>{labelGrade(row.attendance_score)}</td>
                        <td>{row.total_score != null ? row.total_score.toLocaleString('fa-IR') : '—'}</td>
                        <td>{row.pass_fail || '—'}</td>
                        <td>
                          <input
                            type="checkbox"
                            checked={!!row.session_18_absent}
                            disabled={row.session_17_absent}
                            onChange={(e) => updateRow(row.student_id, { session_18_absent: e.target.checked })}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <SkillsHintBlock title="Incomplete" tone="warn">
              غیبت در امتحان عملی یا تستی → وضعیت I؛ دانشجو باید درس را دوباره بگذراند. بدون امتحان مجدد.
            </SkillsHintBlock>
            {studentRows.length > 0 && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="skills-session-18-submit"
                disabled={submitting || !findTransition('session_18_submitted')}
                onClick={handleSession18Submit}
              >
                {submitting ? 'در حال ثبت…' : 'ثبت نمرات جلسه ۱۸ و محاسبه نهایی'}
              </button>
            )}
          </>
        )}

        {currentState === 'ta_evaluation_entry' && (
          <div style={{ marginBottom: '0.85rem' }}>
            <SkillsHintBlock title="کمک‌مدرس" tone="info">
              حضور TA: حداکثر ۸ (منهای ۲ به ازای هر غیبت). وظایف: طرح سؤال، مشورت، جستار/فیلم، وبلاگ.
            </SkillsHintBlock>
            <p style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              نام TA:
              {' '}
              <strong>{taRow?.student_name || skillsCtx.taName || '—'}</strong>
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
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              data-testid="skills-ta-submit"
              disabled={submitting || !findTransition('ta_grades_submitted')}
              onClick={handleTaSubmit}
            >
              {submitting ? 'در حال ثبت…' : 'ثبت نمره TA'}
            </button>
          </div>
        )}

        {currentState === 'qualitative_eval_pending' && (
          <>
            <SkillsHintBlock title="ارزیابی کیفی" tone="info">
              فرم ارزیابی کیفی (سوال ۷ و ۸) را ظرف ۴ روز پس از جلسه ۱۸ برای تک‌تک دانشجویان در فرم پایین صفحه تکمیل کنید.
            </SkillsHintBlock>
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
