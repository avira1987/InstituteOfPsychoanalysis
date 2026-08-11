import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  EducationalTherapistFlowStepper,
  ET_STOP_MESSAGES,
  HintBlock,
  InfoTile,
  ProgressBar,
  resolveUpgradeContext,
  isUpgradeStopState,
  isSystemWaitState,
  fmtIsoDate,
  fmtTimeHm,
  MEETING_TYPE_LABELS,
} from '../utils/upgradeToEducationalTherapistDisplay'

const PROCESS_TITLE_FA = 'ارتقا به درمانگر آموزشی (فرایند ۷۱)'
const PROC_CODE = 'upgrade_to_educational_therapist'

function resolveUpgradeHint(state) {
  if (!state) return 'مراحل ارتقا به درمانگر آموزشی را طبق راهنمای پنل پیش ببرید.'
  if (ET_STOP_MESSAGES[state]) return ET_STOP_MESSAGES[state]
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'مراحل ارتقا به درمانگر آموزشی را طبق راهنمای پنل پیش ببرید.'
}

/**
 * داشبورد راهنمای فرایند ۷۱ — ارتقا به درمانگر آموزشی.
 */
export default function StudentEducationalTherapistUpgradePanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const upgrade = useMemo(() => resolveUpgradeContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'upgrade_to_educational_therapist') {
    return null
  }

  const isStop = isUpgradeStopState(currentState)
  const isComplete = currentState === 'promotion_completed'
  const isWait = isSystemWaitState(currentState)
  const hint = resolveUpgradeHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelState(currentState)) ?? ''

  const showInterview = ['interview_scheduling', 'interview_held'].includes(currentState)
    && (ctx.interview_date || ctx.interview_time)
  const showTherapyProgress = currentState === 'personal_therapy_hours'
  const showSupervisionProgress = currentState === 'supervision_hours'
  const showSlots = currentState === 'et_availability_slots' || isComplete

  return (
    <div
      className="card"
      data-testid="student-educational-therapist-upgrade-panel"
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
        <EducationalTherapistFlowStepper currentState={currentState} />

        {isStop && (
          <HintBlock tone="#dc2626" bg="#fef2f2">
            <strong>پایان مسیر:</strong>
            {' '}
            {hint}
          </HintBlock>
        )}

        {!isStop && !isComplete && (
          <HintBlock tone={isWait ? '#d97706' : '#2563eb'} bg={isWait ? '#fffbeb' : '#eff6ff'}>
            {hint}
          </HintBlock>
        )}

        {isComplete && (
          <HintBlock tone="#16a34a" bg="#f0fdf4">
            ارتقا به درمانگر آموزشی با موفقیت تکمیل شد. دو زمان خالی شما در شیت درمانگران آموزشی ثبت شده است.
          </HintBlock>
        )}

        {currentState === 'student_start' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.65rem', marginBottom: '0.75rem' }}>
            <InfoTile label="وضعیت احراز شرایط" value={upgrade.eligibilitySummary} tone={upgrade.eligibilityMet ? '#16a34a' : '#d97706'} bg={upgrade.eligibilityMet ? '#f0fdf4' : '#fffbeb'} />
          </div>
        )}

        {showInterview && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.65rem', marginBottom: '0.75rem' }}>
            <InfoTile label="تاریخ مصاحبه" value={fmtIsoDate(ctx.interview_date)} />
            <InfoTile label="ساعت" value={fmtTimeHm(ctx.interview_time)} />
            <InfoTile label="نحوه برگزاری" value={MEETING_TYPE_LABELS[ctx.meeting_type] || ctx.meeting_type} />
          </div>
        )}

        {showTherapyProgress && (
          <ProgressBar
            label="پیشرفت ۵۰ ساعت درمان شخصی"
            completed={upgrade.therapyCompleted}
            target={upgrade.therapyTarget}
            pct={upgrade.therapyProgressPct}
          />
        )}

        {showSupervisionProgress && (
          <ProgressBar
            label="پیشرفت ۵۰ ساعت سوپرویژن"
            completed={upgrade.supervisionCompleted}
            target={upgrade.supervisionTarget}
            pct={upgrade.supervisionProgressPct}
          />
        )}

        {currentState === 'therapist_selection' && upgrade.selectedTherapistLabel !== '—' && (
          <InfoTile label="درمانگر پیشنهادی" value={upgrade.selectedTherapistLabel} tone="#7c3aed" bg="#f5f3ff" />
        )}

        {currentState === 'supervisor_selection' && upgrade.selectedSupervisorLabel !== '—' && (
          <InfoTile label="سوپروایزر انتخاب‌شده" value={upgrade.selectedSupervisorLabel} tone="#7c3aed" bg="#f5f3ff" />
        )}

        {showSlots && (upgrade.slot1 || upgrade.slot2) && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.65rem' }}>
            {upgrade.slot1 && (
              <InfoTile
                label="زمان خالی ۱"
                value={`${upgrade.slot1.day || '—'} ${fmtTimeHm(upgrade.slot1.time)}`}
                tone="#16a34a"
                bg="#f0fdf4"
              />
            )}
            {upgrade.slot2 && (
              <InfoTile
                label="زمان خالی ۲"
                value={`${upgrade.slot2.day || '—'} ${fmtTimeHm(upgrade.slot2.time)}`}
                tone="#16a34a"
                bg="#f0fdf4"
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
