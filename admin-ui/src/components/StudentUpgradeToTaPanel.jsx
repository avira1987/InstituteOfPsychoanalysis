import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  TaUpgradeFlowStepper,
  TA_STOP_MESSAGES,
  TA_STATE_HINTS,
  HintBlock,
  InfoTile,
  EligibilityChecklistTiles,
  TrackChips,
  resolveTaUpgradeContext,
  isTaStopState,
  fmtIsoDate,
  fmtTimeHm,
  MEETING_TYPE_LABELS,
} from '../utils/upgradeToTaDisplay'

const PROCESS_TITLE_FA = 'ارتقا به کمک‌مدرس (فرایند ۴۷)'

/**
 * داشبورد راهنمای فرایند ۴۷ — ارتقا به کمک‌مدرس.
 */
export default function StudentUpgradeToTaPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const upgrade = useMemo(() => resolveTaUpgradeContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'upgrade_to_ta') {
    return null
  }

  const isStop = isTaStopState(currentState)
  const isComplete = currentState === 'ta_registered'
  const hint = TA_STOP_MESSAGES[currentState]
    || TA_STATE_HINTS[currentState]
    || 'مراحل ارتقا به کمک‌مدرس را طبق راهنمای این پنل پیش ببرید.'

  const showEligibility = ['student_click', 'conditions_not_met'].includes(currentState)
  const showInterview = ['interview_scheduling', 'interview_held'].includes(currentState)
    && (ctx.interview_date || ctx.interview_time)
  const showTracks = ['track_selection', 'commitment_signature', 'ta_registered'].includes(currentState)
    && upgrade.tracks.length > 0

  return (
    <div
      className="card"
      data-testid="student-upgrade-to-ta-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className={`badge ${isStop ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaUpgradeFlowStepper currentState={currentState} compact={compact} />

        {isStop && (
          <HintBlock tone="#dc2626" bg="#fef2f2">
            <strong>پایان مسیر:</strong>
            {' '}
            {hint}
          </HintBlock>
        )}

        {!isStop && !isComplete && (
          <HintBlock tone="#2563eb" bg="#eff6ff">
            {hint}
          </HintBlock>
        )}

        {isComplete && (
          <HintBlock tone="#16a34a" bg="#f0fdf4">
            ارتقا به کمک‌مدرس با موفقیت تکمیل شد. رسته‌های ثبت‌شده در پروندهٔ شما قابل مشاهده است.
          </HintBlock>
        )}

        {showEligibility && (
          <>
            <EligibilityChecklistTiles items={upgrade.conditionsPreview} />
            {currentState === 'student_click' && (
              <InfoTile
                label="وضعیت کلی احراز"
                value={upgrade.eligibilityMet ? 'همهٔ شروط احراز شده' : 'برخی شروط احراز نشده'}
                tone={upgrade.eligibilityMet ? '#16a34a' : '#d97706'}
                bg={upgrade.eligibilityMet ? '#f0fdf4' : '#fffbeb'}
              />
            )}
          </>
        )}

        {showInterview && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.65rem', marginBottom: '0.75rem' }}>
            <InfoTile label="تاریخ مصاحبه" value={fmtIsoDate(ctx.interview_date)} />
            <InfoTile label="ساعت" value={fmtTimeHm(ctx.interview_time)} />
            <InfoTile label="نحوه برگزاری" value={MEETING_TYPE_LABELS[ctx.meeting_type] || ctx.meeting_type} />
          </div>
        )}

        {showTracks && (
          <div style={{ marginBottom: '0.75rem' }}>
            <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.35rem' }}>رسته‌های توافق‌شده</div>
            <TrackChips tracks={upgrade.tracks} labels={upgrade.trackLabelsFa} />
          </div>
        )}

        {currentState === 'commitment_signature' && (
          <HintBlock tone="#7c3aed" bg="#f5f3ff">
            فرم پایین صفحه را تکمیل کنید: تعهدنامه را بپذیرید، کد پیامکی دریافت و وارد کنید، سپس «ثبت مرحله» و دکمهٔ ادامه را بزنید.
          </HintBlock>
        )}
      </div>
    </div>
  )
}
