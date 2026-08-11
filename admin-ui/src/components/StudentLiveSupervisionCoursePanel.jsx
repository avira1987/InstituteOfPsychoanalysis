import React, { useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  HintBlock,
  InfoTile,
  LiveSupervisionFlowStepper,
  LiveSupervisionSlaBanner,
  labelLiveSupervisionState,
  resolveLiveSupervisionContext,
  isLiveSupervisionProcess,
  isLiveSupervisionViolationState,
  progressBarLabel,
  courseCodeFromContext,
} from '../utils/liveSupervisionCourseCompletionDisplay'

const PROCESS_TITLE_FA = 'خاتمه درس سوپرویژن زنده (فرایند ۶۷)'
const PROC_CODE = 'live_supervision_course_completion'

function resolveLiveSupervisionHint(state) {
  if (!state) return 'وضعیت درس سوپرویژن زنده را در همین صفحه دنبال کنید.'
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'وضعیت درس سوپرویژن زنده را در همین صفحه دنبال کنید.'
}

export default function StudentLiveSupervisionCoursePanel({
  detail = null,
  active = true,
  extraData = null,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const courseCode = courseCodeFromContext(ctx)
  const lmsRoot = extraData?.lms?.live_supervision || {}
  const lmsProgress = courseCode ? (lmsRoot[courseCode] || lmsRoot[String(courseCode)]) : null
  const ls = useMemo(() => resolveLiveSupervisionContext(ctx, lmsProgress), [ctx, lmsProgress])
  const [progressRow, setProgressRow] = useState(null)

  useEffect(() => {
    if (!active || !courseCode) return
    panelApi.liveSupervisionProgress(courseCode)
      .then((res) => {
        const rows = res.data?.progress || []
        const sid = detail?.student_id
        const match = rows.find((r) => String(r.student_id) === String(sid))
        if (match) setProgressRow(match)
      })
      .catch(() => setProgressRow(null))
  }, [active, courseCode, detail?.student_id])

  if (!active || !detail || !isLiveSupervisionProcess(detail.process_code)) {
    return null
  }

  const hint = resolveLiveSupervisionHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelLiveSupervisionState(currentState)) ?? ''
  const isComplete = currentState === 'completed'
  const prog = progressRow || ls

  return (
    <div className="card" data-testid="student-live-supervision-course-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isComplete ? 'badge-success' : isLiveSupervisionViolationState(currentState) ? 'badge-danger' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelLiveSupervisionState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <LiveSupervisionFlowStepper currentState={currentState} compact={compact} />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.65rem',
          }}
        >
          <InfoTile label="درس" value={ls.courseName} tone="#0d9488" bg="#f0fdfa" />
          <InfoTile
            label="پیشرفت حضور"
            value={progressBarLabel(prog.normal_count ?? ls.normalCount, prog.mirror_count ?? ls.mirrorCount)}
            tone="#7c3aed"
            bg="#f5f3ff"
          />
          {Number(prog.compensation_pending ?? ls.compensationPending) > 0 && (
            <InfoTile
              label="پرداخت جبرانی"
              value={`${prog.compensation_pending ?? ls.compensationPending} جلسه غیبت`}
              tone="#dc2626"
              bg="#fef2f2"
            />
          )}
        </div>

        <LiveSupervisionSlaBanner ctx={ctx} currentState={currentState} startedAt={detail.started_at} />

        {ls.compensationUrl && Number(ls.compensationPending) > 0 && (
          <HintBlock tone="warn">
            برای تکمیل بسته ۱۸ جلسه‌ای، پرداخت جبرانی غیبت‌ها لازم است.
            {' '}
            <a href={ls.compensationUrl}>رفتن به صفحه پرداخت</a>
          </HintBlock>
        )}

        <HintBlock tone={isLiveSupervisionViolationState(currentState) ? 'danger' : 'info'}>
          {hint}
        </HintBlock>
      </div>
    </div>
  )
}
