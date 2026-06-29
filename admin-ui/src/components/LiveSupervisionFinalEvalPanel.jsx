import React, { useMemo } from 'react'
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
  isLiveSupervisionProcess,
  progressBarLabel,
} from '../utils/liveSupervisionCourseCompletionDisplay'

const HINT = 'هجدهمین حضور این دانشجو ثبت شد. فرم ارزیابی کیفی (سوال ۷ و ۸) را تا ساعت ۲۴:۰۰ همین روز تکمیل کنید.'

/** راهنمای state final_eval_pending — فرم Q7/Q8 در OperatorStepFormsSection */
export default function LiveSupervisionFinalEvalPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const ls = useMemo(() => resolveLiveSupervisionContext(ctx), [ctx])
  const evalSummary = useMemo(() => resolveEvaluationSummary(ctx), [ctx])

  if (!active || !detail || !isLiveSupervisionProcess(detail.process_code)) return null
  if (currentState !== 'final_eval_pending') return null

  return (
    <div
      className="card"
      data-testid="live-supervision-final-eval-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem', border: '2px solid #0d9488' }}
    >
      <div className="card-header">
        <h3 className="card-title">ارزیابی نهایی کیفی — سوپرویژن زنده</h3>
        <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
          {labelLiveSupervisionState(currentState) || labelState(currentState)}
        </span>
      </div>
      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <LiveSupervisionFlowStepper currentState={currentState} compact={compact} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.65rem', marginBottom: '0.75rem' }}>
          <InfoTile label="دانشجو" value={ls.studentName} tone="#2563eb" bg="#eff6ff" />
          <InfoTile label="پیشرفت" value={progressBarLabel(ls.normalCount, ls.mirrorCount)} tone="#7c3aed" bg="#f5f3ff" />
        </div>
        <LiveSupervisionSlaBanner ctx={ctx} currentState={currentState} startedAt={detail.started_at} />
        <HintBlock tone="warn">{HINT}</HintBlock>
        <EvaluationSummaryBlock summary={evalSummary} />
      </div>
    </div>
  )
}
