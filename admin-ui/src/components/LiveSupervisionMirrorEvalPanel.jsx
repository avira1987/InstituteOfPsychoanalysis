import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  HintBlock,
  InfoTile,
  LiveSupervisionFlowStepper,
  LiveSupervisionSlaBanner,
  labelLiveSupervisionState,
  resolveLiveSupervisionContext,
  isLiveSupervisionProcess,
  isLiveSupervisionViolationState,
} from '../utils/liveSupervisionCourseCompletionDisplay'

const HINT = 'پس از ثبت سومین جلسه پشت‌آینه، ظرف ۵ روز فرم ارزیابی بالینی را تکمیل کنید و «ثبت ارزیابی» را بزنید.'

/** راهنمای state mirror_eval_pending — فرم در OperatorStepFormsSection */
export default function LiveSupervisionMirrorEvalPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const ls = useMemo(() => resolveLiveSupervisionContext(ctx), [ctx])

  if (!active || !detail || !isLiveSupervisionProcess(detail.process_code)) return null
  if (currentState !== 'mirror_eval_pending') return null

  return (
    <div
      className="card"
      data-testid="live-supervision-mirror-eval-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">ارزیابی ۳ جلسه پشت‌آینه</h3>
        <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
          {labelLiveSupervisionState(currentState) || labelState(currentState)}
        </span>
      </div>
      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <LiveSupervisionFlowStepper currentState={currentState} compact={compact} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.65rem', marginBottom: '0.75rem' }}>
          <InfoTile label="دانشجو" value={ls.studentName} tone="#2563eb" bg="#eff6ff" />
          <InfoTile label="درس" value={ls.courseName} tone="#0d9488" bg="#f0fdfa" />
        </div>
        <LiveSupervisionSlaBanner ctx={ctx} currentState={currentState} startedAt={detail.started_at} />
        <HintBlock tone="warn">{HINT}</HintBlock>
      </div>
    </div>
  )
}
