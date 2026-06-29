import React, { useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import { labelState } from '../utils/processDisplay'
import {
  EvaluationSummaryBlock,
  HintBlock,
  InfoTile,
  LiveSupervisionFlowStepper,
  LiveSupervisionSlaBanner,
  labelLiveSupervisionState,
  resolveEvaluationSummary,
  resolveLiveSupervisionContext,
  isLiveSupervisionViolationState,
  isLiveSupervisionProcess,
  progressBarLabel,
  NORMAL_REQUIRED,
  MIRROR_REQUIRED,
} from '../utils/liveSupervisionCourseCompletionDisplay'

const PROCESS_TITLE_FA = 'خاتمه درس سوپرویژن زنده (فرایند ۶۷)'

const INSTRUCTOR_STATE_HINTS = {
  sessions_in_progress:
    'در هر جلسه حضور دوگانه (عادی / پشت‌آینه) را ثبت کنید. پس از ۱۵ عادی + ۳ پشت‌آینه برای هر دانشجو، فرم ارزیابی نهایی باز می‌شود.',
  mirror_eval_pending:
    'پس از ثبت سومین جلسه پشت‌آینه، ظرف ۵ روز فرم ارزیابی بالینی را تکمیل کنید.',
  final_eval_pending:
    'فرم ارزیابی کیفی نهایی (سوال ۷ و ۸) را تا ساعت ۲۴:۰۰ همان روز تکمیل کنید.',
  completed: 'ارزیابی نهایی ثبت شد و درس برای این دانشجو تکمیل گردید.',
  mirror_eval_violation: 'تأخیر در ارزیابی پشت‌آینه — گزارش به کمیته نظارت ارسال شده است.',
  final_eval_delay: 'تأخیر ارزیابی نهایی — مسئول علمی کمیته دروس مطلع شده است.',
}

export default function LiveSupervisionCourseCompletionPanel({
  detail = null,
  active = true,
  portalRole = 'staff',
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const ls = useMemo(() => resolveLiveSupervisionContext(ctx), [ctx])
  const evalSummary = useMemo(() => resolveEvaluationSummary(ctx), [ctx])
  const [classProgress, setClassProgress] = useState([])
  const [loadingProgress, setLoadingProgress] = useState(false)

  const courseCode = ls.courseCode

  useEffect(() => {
    if (!active || !isLiveSupervisionProcess(detail?.process_code) || !courseCode) return
    let cancelled = false
    setLoadingProgress(true)
    panelApi.liveSupervisionProgress(courseCode)
      .then((res) => {
        if (!cancelled) setClassProgress(res.data?.progress || [])
      })
      .catch(() => {
        if (!cancelled) setClassProgress([])
      })
      .finally(() => {
        if (!cancelled) setLoadingProgress(false)
      })
    return () => { cancelled = true }
  }, [active, detail?.process_code, courseCode])

  if (!active || !detail || !isLiveSupervisionProcess(detail.process_code)) {
    return null
  }

  const bucket = (portalRole || '').toLowerCase()
  if (!['instructor', 'admin', 'staff', 'teaching_assistant'].includes(bucket)) return null

  const hint = INSTRUCTOR_STATE_HINTS[currentState]
    ?? 'خاتمه درس سوپرویژن زنده — طبق راهنمای مرحله و فرم پایین اقدام کنید.'
  const isTerminal = currentState === 'completed' || isLiveSupervisionViolationState(currentState)

  return (
    <div
      className="card"
      data-testid="live-supervision-course-completion-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelLiveSupervisionState(currentState) || labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <LiveSupervisionFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          <InfoTile label="درس" value={ls.courseName} tone="#0d9488" bg="#f0fdfa" />
          {ls.studentName && (
            <InfoTile label="دانشجو (پرونده)" value={ls.studentName} tone="#2563eb" bg="#eff6ff" />
          )}
          <InfoTile
            label="پیشرفت این پرونده"
            value={progressBarLabel(ls.normalCount, ls.mirrorCount)}
            tone="#7c3aed"
            bg="#f5f3ff"
          />
        </div>

        <LiveSupervisionSlaBanner ctx={ctx} currentState={currentState} startedAt={detail.started_at} />

        {currentState === 'sessions_in_progress' && (
          <HintBlock tone="info">
            لیست کلاس بر اساس سال ورود (قدیمی‌تر اول) و تجربه بالینی مرتب می‌شود. هر دانشجو باید دقیقاً
            {' '}
            {NORMAL_REQUIRED.toLocaleString('fa-IR')}
            {' '}
            جلسه عادی و
            {' '}
            {MIRROR_REQUIRED.toLocaleString('fa-IR')}
            {' '}
            جلسه پشت‌آینه را تکمیل کند.
          </HintBlock>
        )}

        {hint && (
          <HintBlock tone={isLiveSupervisionViolationState(currentState) ? 'danger' : 'info'}>
            {hint}
          </HintBlock>
        )}

        {courseCode && (
          <div style={{ marginBottom: '0.85rem' }}>
            <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.5rem' }}>
              پیشرفت کلاس
            </div>
            {loadingProgress ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری…</p>
            ) : classProgress.length === 0 ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>هنوز دانشجویی در این درس ثبت نشده است.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.82rem' }}>
                  <thead>
                    <tr>
                      <th>ردیف</th>
                      <th>نام</th>
                      <th>ورودی</th>
                      <th>عادی</th>
                      <th>پشت‌آینه</th>
                      <th>غیبت</th>
                      <th>جبرانی</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {classProgress.map((row, idx) => (
                      <tr key={row.student_id || idx}>
                        <td>{(idx + 1).toLocaleString('fa-IR')}</td>
                        <td>{row.student_name || '—'}</td>
                        <td>{row.admission_cohort != null ? String(row.admission_cohort) : '—'}</td>
                        <td>{Number(row.normal_count || 0).toLocaleString('fa-IR')}</td>
                        <td>{Number(row.mirror_count || 0).toLocaleString('fa-IR')}</td>
                        <td>{Number(row.absences || 0).toLocaleString('fa-IR')}</td>
                        <td>
                          {Number(row.compensation_pending || 0) > 0
                            ? `${row.compensation_pending} جلسه`
                            : '—'}
                        </td>
                        <td>{row.is_complete ? 'تکمیل' : 'در جریان'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        <EvaluationSummaryBlock summary={evalSummary} />
      </div>
    </div>
  )
}
