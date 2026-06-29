import React, { useMemo } from 'react'
import { formatStudentCodeDisplay, labelState } from '../utils/processDisplay'
import {
  TaAssistantFlowStepper,
  TA_ASSISTANT_COMMITTEE_HINTS,
  resolveTaUpgradeContext,
  HintBlock,
  InfoTile,
} from '../utils/taToAssistantFacultyDisplay'

const ACCENT = '#d97706'
const ACCENT_BG = '#fffbeb'

/**
 * راهنمای کمیته نظارت — فرایند ۴۹.
 */
export default function TaToAssistantFacultyReviewPanel({
  detail = null,
  user = null,
  active = true,
  compact = false,
}) {
  const currentState = detail?.current_state
  const ctx = detail?.context_data || {}

  const upgrade = useMemo(() => resolveTaUpgradeContext(ctx), [ctx])

  if (
    !active
    || !detail
    || detail.process_code !== 'ta_to_assistant_faculty'
    || currentState !== 'supervision_review'
  ) {
    return null
  }

  const studentLabel = detail?.student_code
    ? formatStudentCodeDisplay(detail.student_code)
    : null
  const hint = TA_ASSISTANT_COMMITTEE_HINTS.supervision_review

  return (
    <div
      className="card"
      data-testid="ta-assistant-faculty-review-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">بررسی ارتقا به دستیار هیئت علمی (فرایند ۴۹)</h3>
        {!compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaAssistantFlowStepper currentState={currentState} />

        <HintBlock tone={ACCENT} bg={ACCENT_BG}>
          {hint}
        </HintBlock>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.75rem',
          }}
        >
          {studentLabel && (
            <InfoTile label="پروندهٔ دانشجو" value={studentLabel} tone="#2563eb" bg="#eff6ff" />
          )}
          <InfoTile label="نام درس" value={upgrade.courseName} tone="#2563eb" bg="#eff6ff" />
          <InfoTile label="سابقه TA" value={upgrade.passSummary} tone="#16a34a" bg="#f0fdf4" />
          <InfoTile label="رتبه تحلیلی فعلی" value={upgrade.currentRankFa} tone="#7c3aed" bg="#f5f3ff" />
        </div>

        {upgrade.alreadyAssistant && (
          <HintBlock tone="#7c3aed" bg="#f5f3ff">
            متقاضی قبلاً رتبهٔ «دستیار هیئت علمی» دارد؛ در این پرونده فقط صلاحیت تدریس درس
            {' '}
            <strong>{upgrade.courseName}</strong>
            {' '}
            بررسی می‌شود.
          </HintBlock>
        )}

        {upgrade.summaryFa !== '—' && (
          <p style={{ fontSize: '0.82rem', margin: '0 0 0.5rem', color: '#64748b' }}>
            خلاصه احراز خودکار:
            {' '}
            <strong>{upgrade.summaryFa}</strong>
          </p>
        )}

        {user?.role && user.role !== 'supervision_committee' && user.role !== 'admin' && (
          <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
            این مرحله معمولاً بر عهدهٔ کمیته نظارت است.
          </p>
        )}
      </div>
    </div>
  )
}
