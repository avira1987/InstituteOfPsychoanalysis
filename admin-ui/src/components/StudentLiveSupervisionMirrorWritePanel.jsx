import React, { useMemo } from 'react'
import {
  HintBlock,
  InfoTile,
  LiveSupervisionSlaBanner,
  labelLiveSupervisionState,
  resolveLiveSupervisionContext,
  isLiveSupervisionProcess,
} from '../utils/liveSupervisionCourseCompletionDisplay'

const TITLE = 'پیاده‌سازی جلسه پشت‌آینه'

/** راهنمای state mirror_implementation_pending — فرم در ProcessStepFormsSection */
export default function StudentLiveSupervisionMirrorWritePanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const ls = useMemo(() => resolveLiveSupervisionContext(ctx), [ctx])

  if (!active || !detail || !isLiveSupervisionProcess(detail.process_code)) return null
  if (currentState !== 'mirror_implementation_pending') return null

  const sessionLabel = ls.mirrorSessionIndex != null
    ? `جلسه ${Number(ls.mirrorSessionIndex).toLocaleString('fa-IR')} پشت‌آینه`
    : 'جلسه پشت‌آینه'

  return (
    <div className="card" data-testid="student-live-supervision-mirror-write-panel">
      <div className="card-header">
        <h3 className="card-title">{TITLE}</h3>
        <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
          {labelLiveSupervisionState(currentState)}
        </span>
      </div>
      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <InfoTile label="درس" value={ls.courseName} tone="#0d9488" bg="#f0fdfa" />
        <InfoTile label="جلسه" value={sessionLabel} tone="#2563eb" bg="#eff6ff" />
        <LiveSupervisionSlaBanner ctx={ctx} currentState={currentState} startedAt={detail.started_at} />
        <HintBlock tone="warn">
          لطفاً جلسه پشت آینه خود را پیاده‌سازی کنید. متن را در فرم پایین وارد کرده و «ادامه و ثبت مرحله» را بزنید.
        </HintBlock>
      </div>
    </div>
  )
}
