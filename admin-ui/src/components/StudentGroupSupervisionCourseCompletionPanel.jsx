import React, { useMemo } from 'react'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  HOURS_PER_PASS_DISPLAY,
  PROCESS_TITLE_FA,
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

const PROC_CODE = 'group_supervision_course_completion'

function resolveGroupSupervisionHint(state) {
  if (!state) return 'خاتمه درس سوپرویژن گروهی — وضعیت پرونده را در همین صفحه دنبال کنید.'
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'خاتمه درس سوپرویژن گروهی — وضعیت پرونده را در همین صفحه دنبال کنید.'
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

  const hint = resolveGroupSupervisionHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelGroupSupervisionState(currentState)) ?? ''
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
        <GroupSupervisionHintBlock title="اقدام بعدی شما">
          {statusShort && (
            <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>
              وضعیت فعلی: {statusShort}
            </div>
          )}
          {hint}
        </GroupSupervisionHintBlock>
        <p style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '0.5rem' }}>
          {hoursSummaryLabel()}
        </p>
      </div>
    </div>
  )
}
