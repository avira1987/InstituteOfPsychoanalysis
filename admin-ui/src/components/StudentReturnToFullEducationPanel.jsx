import React, { useMemo } from 'react'
import SepPaymentPanel from './SepPaymentPanel'
import { labelState } from '../utils/processDisplay'
import {
  ReturnFlowStepper,
  RETURN_STATE_HINTS,
  HintBlock,
  InfoTile,
  ScheduleChip,
  resolveReturnContext,
  isReturnCompleteState,
  isSystemWaitState,
  fmtIsoDate,
  fmtTimeHm,
  fmtRialAsToman,
} from '../utils/returnToFullEducationDisplay'

const PROCESS_TITLE_FA = 'بازگشت به کل آموزش پس از مرخصی (فرایند ۶۰)'

/**
 * داشبورد راهنمای فرایند ۶۰ — بازگشت به کل آموزش.
 */
export default function StudentReturnToFullEducationPanel({
  detail = null,
  studentProfile = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const ret = useMemo(() => resolveReturnContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'return_to_full_education') {
    return null
  }

  const isComplete = isReturnCompleteState(currentState)
  const isWait = isSystemWaitState(currentState)
  const hint = RETURN_STATE_HINTS[currentState]
    || 'مراحل بازگشت به کل آموزش را طبق راهنمای پنل پیش ببرید.'

  const showTherapySummary = [
    'therapy_payment_pending',
    'therapy_completed',
    'supervisor_selection',
    'supervision_24h_scheduled',
    'supervision_payment_pending',
    'registration_unlocked',
    'return_complete',
  ].includes(currentState)

  const showSupervisionSection = ret.isIntern && [
    'supervisor_selection',
    'supervision_24h_scheduled',
    'supervision_payment_pending',
    'registration_unlocked',
    'return_complete',
  ].includes(currentState)

  const studentId = studentProfile?.id || detail?.student_id

  return (
    <div
      className="card"
      data-testid="student-return-to-full-education-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isComplete ? 'badge-success' : isWait ? 'badge-warning' : 'badge-info'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ReturnFlowStepper currentState={currentState} compact={compact} />

        {!isComplete && (
          <HintBlock tone={isWait ? '#d97706' : '#2563eb'} bg={isWait ? '#fffbeb' : '#eff6ff'}>
            {hint}
          </HintBlock>
        )}

        {isComplete && (
          <HintBlock tone="#16a34a" bg="#f0fdf4">
            بازگشت به کل آموزش با موفقیت تکمیل شد. ثبت‌نام دروس ترم جدید برای شما باز شده است.
          </HintBlock>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.75rem',
          }}
        >
          <InfoTile label="نوع دوره" value={ret.courseTypeLabel} tone="#0d9488" bg="#f0fdfa" />
          <InfoTile label="وضعیت بالینی" value={ret.isInternLabel} tone="#7c3aed" bg="#f5f3ff" />
          {currentState === 'therapist_selection' && (
            <InfoTile label="محدودیت ساعات درمان" value={ret.weeklyHoursHint} tone="#d97706" bg="#fffbeb" />
          )}
          {showSupervisionSection && currentState === 'supervisor_selection' && (
            <InfoTile label="محدودیت سوپرویژن" value={ret.supervisionHoursHint} tone="#d97706" bg="#fffbeb" />
          )}
        </div>

        {showTherapySummary && (ret.therapistName || ret.therapyFirstSessionAt) && (
          <div
            data-testid="return-therapy-summary"
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.55rem',
              marginBottom: '0.85rem',
            }}
          >
            {ret.therapistName && (
              <ScheduleChip label="درمانگر آموزشی" value={ret.therapistName} tone="#7c3aed" bg="#f5f3ff" />
            )}
            {ret.therapyFirstSessionAt && (
              <ScheduleChip label="شروع درمان" value={fmtIsoDate(ret.therapyFirstSessionAt)} tone="#0d9488" bg="#f0fdfa" />
            )}
            {ret.therapyPaymentRial > 0 && currentState === 'therapy_payment_pending' && (
              <ScheduleChip label="مبلغ جلسه اول" value={fmtRialAsToman(ret.therapyPaymentRial)} />
            )}
          </div>
        )}

        {showSupervisionSection && (ret.supervisorName || ret.supervisionFirstSessionAt) && (
          <div
            data-testid="return-supervision-summary"
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.55rem',
              marginBottom: '0.85rem',
            }}
          >
            {ret.supervisorName && (
              <ScheduleChip label="سوپروایزر" value={ret.supervisorName} tone="#7c3aed" bg="#f5f3ff" />
            )}
            {ret.supervisionDay && (
              <ScheduleChip label="روز جلسه" value={ret.supervisionDay} />
            )}
            {ret.supervisionTime && (
              <ScheduleChip label="ساعت جلسه" value={fmtTimeHm(ret.supervisionTime)} />
            )}
            {ret.supervisionFirstSessionAt && (
              <ScheduleChip
                label="شروع سوپرویژن"
                value={fmtIsoDate(ret.supervisionFirstSessionAt)}
                tone="#0d9488"
                bg="#f0fdfa"
              />
            )}
          </div>
        )}

        {currentState === 'therapy_payment_pending' && studentId && (
          <div style={{ marginBottom: '0.85rem' }} data-testid="return-therapy-sep-payment">
            <SepPaymentPanel
              instanceId={detail.instance_id}
              studentId={studentId}
              amountRial={ret.therapyPaymentRial > 0 ? ret.therapyPaymentRial : undefined}
              description="پرداخت جلسه اول درمان آموزشی (بازگشت به کل آموزش)"
            />
          </div>
        )}

        {currentState === 'supervision_payment_pending' && studentId && (
          <div style={{ marginBottom: '0.85rem' }} data-testid="return-supervision-sep-payment">
            <SepPaymentPanel
              instanceId={detail.instance_id}
              studentId={studentId}
              amountRial={ret.supervisionPaymentRial > 0 ? ret.supervisionPaymentRial : undefined}
              description="پرداخت جلسه اول سوپرویژن (بازگشت به کل آموزش)"
            />
          </div>
        )}

        {currentState === 'registration_unlocked' && ret.registrationUnlockedAt && (
          <InfoTile
            label="زمان بازگشایی ثبت‌نام"
            value={fmtIsoDate(ret.registrationUnlockedAt)}
            tone="#16a34a"
            bg="#f0fdf4"
          />
        )}
      </div>
    </div>
  )
}
