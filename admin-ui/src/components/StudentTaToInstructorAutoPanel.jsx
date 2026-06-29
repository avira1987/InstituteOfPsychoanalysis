import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  TaToInstructorFlowStepper,
  TA_TO_INSTRUCTOR_STATE_HINTS,
  TA_TO_INSTRUCTOR_CONGRATS_FA,
  HintBlock,
  InfoTile,
  resolveTaToInstructorContext,
  labelTaToInstructorState,
} from '../utils/taToInstructorAutoDisplay'

const PROCESS_TITLE_FA = 'تبدیل کمک‌مدرس به مدرس (فرایند ۵۰)'

/**
 * داشبورد راهنمای فرایند ۵۰ — تبدیل خودکار کمک‌مدرس به مدرس در هر درس.
 */
export default function StudentTaToInstructorAutoPanel({
  detail = null,
  extraData = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const resolved = useMemo(
    () => resolveTaToInstructorContext(ctx, extraData || {}),
    [ctx, extraData],
  )

  if (!active || !detail || detail.process_code !== 'ta_to_instructor_auto') {
    return null
  }

  const isComplete = currentState === 'upgrade_applied'
  const isFailed = currentState === 'conditions_not_met'
  const hint = TA_TO_INSTRUCTOR_STATE_HINTS[currentState]
    || 'فرایند ارتقای خودکار کمک‌مدرس به مدرس — این صفحه را بعداً تازه کنید.'

  return (
    <div
      className="card"
      data-testid="student-ta-to-instructor-auto-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isFailed ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelTaToInstructorState(currentState) || labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaToInstructorFlowStepper currentState={currentState} compact={compact} />

        {isFailed && (
          <HintBlock tone="#dc2626" bg="#fef2f2">
            <strong>شرایط احراز نشد:</strong>
            {' '}
            {hint}
            {resolved.eligibilitySummary !== '—' && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.82rem' }}>{resolved.eligibilitySummary}</div>
            )}
          </HintBlock>
        )}

        {!isFailed && !isComplete && (
          <HintBlock tone="#d97706" bg="#fffbeb">{hint}</HintBlock>
        )}

        {isComplete && (
          <HintBlock tone="#16a34a" bg="#f0fdf4">
            <strong>تبریک!</strong>
            {' '}
            {TA_TO_INSTRUCTOR_CONGRATS_FA}
          </HintBlock>
        )}

        {(isComplete || currentState === 'end_of_term_check') && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '0.65rem',
              marginBottom: '0.75rem',
            }}
          >
            <InfoTile label="رتبه تحلیلی" value={resolved.rankLabel} tone="#7c3aed" bg="#f5f3ff" />
            <InfoTile label="درس مبدأ" value={resolved.sourceCourseName} />
            <InfoTile label="رسته" value={resolved.trackName} tone="#0d9488" bg="#f0fdfa" />
            {isComplete && (
              <>
                <InfoTile label="نقش جدید" value={resolved.promotedRole} tone="#16a34a" bg="#f0fdf4" />
                <InfoTile label="درس بعدی (بازشده)" value={resolved.nextCourseName} tone="#2563eb" bg="#eff6ff" />
              </>
            )}
          </div>
        )}

        {currentState === 'end_of_term_check' && (
          <p style={{ fontSize: '0.82rem', color: '#64748b', margin: 0, lineHeight: 1.7 }}>
            این فرایند ۱۰۰٪ خودکار است و نیازی به اقدام از سمت شما ندارد.
          </p>
        )}
      </div>
    </div>
  )
}
