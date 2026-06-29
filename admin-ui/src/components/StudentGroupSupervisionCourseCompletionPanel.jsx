import React, { useMemo } from 'react'
import {
  HOURS_PER_PASS_DISPLAY,
  PROCESS_TITLE_FA,
  STATE_HINTS,
  GroupSupervisionFlowStepper,
  GroupSupervisionHintBlock,
  GroupSupervisionSlaBanner,
  InfoTile,
  fmtHours,
  hoursSummaryLabel,
  isTerminalState,
  labelGroupSupervisionState,
  labelPassFail,
  resolveGroupSupervisionContext,
} from '../utils/groupSupervisionCourseCompletionDisplay'

const STUDENT_STATE_HINTS = {
  awaiting_session_18:
    'درس شما در انتظار جلسه ۱۸ است. پس از برگزاری، مدرس وضعیت Pass/Fail را ثبت می‌کند.',
  session_18_pass_fail_entry:
    'جلسه ۱۸ — مدرس در حال ثبت Pass/Fail مشارکت است (مهلت ۲۴ ساعت).',
  pass_fail_applied: 'نتایج در حال اعمال در پرونده است.',
  ta_evaluation_entry: 'مدرس در حال ارزیابی کمک‌مدرس است.',
  qualitative_eval_pending: 'مدرس فرم ارزیابی کیفی را تکمیل می‌کند.',
  grades_locked: 'نتیجه نهایی ثبت و قفل شد.',
  session_18_delay: 'مهلت ثبت Pass/Fail گذشته است. با دفتر آموزش تماس بگیرید.',
  qualitative_eval_delay: 'تأخیر در ارزیابی کیفی. با دفتر آموزش تماس بگیرید.',
}

/**
 * داشبورد راهنمای «خاتمه هر درس سوپرویژن گروهی» — فرایند ۶۲ (دانشجو).
 */
export default function StudentGroupSupervisionCourseCompletionPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const gsCtx = useMemo(() => resolveGroupSupervisionContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'group_supervision_course_completion') {
    return null
  }

  const hint = STUDENT_STATE_HINTS[currentState] || STATE_HINTS[currentState]
    || 'خاتمه درس سوپرویژن گروهی — وضعیت پرونده را در همین صفحه دنبال کنید.'
  const isTerminal = isTerminalState(currentState)

  const myRow = (gsCtx.studentsGrades || []).find(
    (r) => String(r.student_id) === String(detail.student_id),
  ) || {}
  const passFail = myRow.pass_fail ?? myRow.grade
  const hoursBefore = myRow.group_supervision_hours_before
  const hoursAfter = myRow.hours_after

  return (
    <div className="card" data-testid="student-group-supervision-panel">
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
          <InfoTile label="وضعیت شما" value={labelPassFail(passFail)} tone={passFail === 'PASS' ? '#059669' : '#dc2626'} />
          {passFail === 'PASS' && (
            <InfoTile
              label="ساعات پس از Pass"
              value={`+${HOURS_PER_PASS_DISPLAY}`}
              tone="#7c3aed"
              bg="#f5f3ff"
            />
          )}
          {hoursAfter != null && (
            <InfoTile label="جمع ساعات گروهی" value={fmtHours(hoursAfter)} tone="#2563eb" bg="#eff6ff" />
          )}
          {hoursBefore != null && !hoursAfter && (
            <InfoTile label="ساعات فعلی" value={fmtHours(hoursBefore)} tone="#2563eb" bg="#eff6ff" />
          )}
        </div>

        <GroupSupervisionSlaBanner ctx={ctx} currentState={currentState} startedAt={detail.started_at} />
        <GroupSupervisionHintBlock>{hint}</GroupSupervisionHintBlock>
        <p style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '0.5rem' }}>
          {hoursSummaryLabel()}
        </p>
      </div>
    </div>
  )
}
