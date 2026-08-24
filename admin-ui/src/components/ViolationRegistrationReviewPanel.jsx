import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import { ReadonlyRow, SlaBanner } from '../utils/earlyTerminationChainDisplay'
import {
  ViolationFlowStepper,
  labelViolationState,
  resolveViolationContext,
  computeFirstActionSlaRemaining,
  computeCompensatorySlaRemaining,
  fmtMeetingDateTime,
  meetingModeLabel,
  StudentPerformanceLogTable,
  FIRST_ACTION_SLA_DAYS,
  COMPENSATORY_SLA_DAYS,
} from '../utils/violationRegistrationDisplay'

const ACCENT = '#b91c1c'
const ACCENT_BG = '#fef2f2'
const ACCENT_TEXT = '#991b1b'

const STATE_HINTS = {
  violation_reported:
    'فرم «بررسی اولیه» را تکمیل کنید. اگر قابل بررسی نیست «ثبت و مختومه»؛ اگر قابل بررسی است «در حال بررسی» را بزنید. مهلت اقدام اول: ۳ روز.',
  review_status_set:
    'نیاز به جلسه را مشخص کنید. با «بله» پس از ثبت فرم «تنظیم جلسه» را بزنید؛ با «خیر» حکم را در همان فرم انتخاب و «صدور حکم مستقیم» را بزنید.',
  meeting_scheduled:
    'پس از برگزاری جلسه با دانشجو، فرم «صدور حکم» را تکمیل و دکمهٔ «صدور حکم» را بزنید.',
  verdict_issued:
    'برای تذکر/اخطار «ثبت و مختومه»؛ برای تعلیق یا ارجاع به کمیته آموزش دکمهٔ متناسب با حکم ثبت‌شده را بزنید. پیگیری شروط جبرانی: ۷ روز.',
  suspension_next_term:
    'ثبت‌نام ترم بعد و حضور سوپرویژن قفل شده است. پس از پیگیری، تعلیق را بردارید یا به کمیته آموزش ارجاع دهید.',
  suspension_immediate:
    'حضور در کلاس‌ها و سوپرویژن قفل شده است. پس از پیگیری شروط جبرانی، تعلیق را بردارید یا ارجاع دهید.',
  referred_to_education_committee:
    'جلسه کمیته آموزش همیشه آنلاین است. فرم حکم نهایی را تکمیل و «عدم اخراج» یا «اخراج» را بزنید.',
  closed: 'پرونده مختومه شد.',
  expelled: 'حکم اخراج اجرا شد؛ پورتال دانشجو فقط‌خواندنی است.',
}

/**
 * داشبورد راهنمای «ثبت تخلفات» — فرایند ۵۵ (کمیته نظارت / آموزش).
 */
export default function ViolationRegistrationReviewPanel({
  detail = null,
  stepFormValues = {},
  studentExtraData = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const vr = useMemo(
    () => resolveViolationContext({ ...ctx, ...stepFormValues }),
    [ctx, stepFormValues],
  )

  const firstActionSla = useMemo(
    () => (currentState === 'violation_reported' ? computeFirstActionSlaRemaining(ctx) : null),
    [currentState, ctx],
  )
  const compensatorySla = useMemo(
    () => (currentState === 'verdict_issued' ? computeCompensatorySlaRemaining(ctx) : null),
    [currentState, ctx],
  )

  const performanceLog = useMemo(() => {
    const fromExtra = studentExtraData?.monitoring_performance_log
    if (Array.isArray(fromExtra) && fromExtra.length) return fromExtra
    return []
  }, [studentExtraData])

  if (!active || !detail || detail.process_code !== 'violation_registration') {
    return null
  }

  const hint = STATE_HINTS[currentState]
    ?? 'پروندهٔ ثبت تخلف — بررسی طبق دستور کار کمیته نظارت.'
  const isTerminal = currentState === 'closed' || currentState === 'expelled'

  return (
    <div
      className="card"
      data-testid="violation-registration-review-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">ثبت تخلفات (فرایند ۵۵)</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelState(currentState) || labelViolationState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ViolationFlowStepper currentState={currentState} compact={compact} />

        {currentState === 'violation_reported' && (
          <SlaBanner
            slaInfo={firstActionSla}
            title={`مهلت اقدام اول (${FIRST_ACTION_SLA_DAYS} روز)`}
            fallbackText="کمیته نظارت ۳ روز برای ثبت اولین اقدام فرصت دارد."
          />
        )}

        {currentState === 'verdict_issued' && (
          <SlaBanner
            slaInfo={compensatorySla}
            title={`پیگیری شروط جبرانی (${COMPENSATORY_SLA_DAYS} روز)`}
            fallbackText="پس از ۷ روز از صدور حکم، پیگیری شروط جبرانی در پورتال یادآوری می‌شود."
          />
        )}

        {hint && !isTerminal && (
          <div
            data-testid="violation-committee-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: ACCENT_BG,
              borderRight: `4px solid ${ACCENT}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: ACCENT_TEXT,
            }}
          >
            {hint}
          </div>
        )}

        <div
          data-testid="violation-dossier"
          style={{
            marginBottom: '0.85rem',
            padding: '0.85rem 1rem',
            borderRadius: '10px',
            background: '#f8fafc',
            borderRight: '4px solid #64748b',
            fontSize: '0.84rem',
            lineHeight: 1.75,
          }}
        >
          <strong style={{ display: 'block', marginBottom: '0.5rem' }}>خلاصهٔ پرونده</strong>
          <ReadonlyRow label="منبع ارجاع" value={vr.sourceReason} testId="violation-source-reason" />
          <ReadonlyRow label="فرایند مبدأ" value={vr.sourceProcessCode} testId="violation-source-process" />
          {vr.parentInstanceId && (
            <ReadonlyRow
              label="نمونهٔ والد"
              value={String(vr.parentInstanceId)}
              testId="violation-parent-instance"
            />
          )}
          <ReadonlyRow label="نوع تخلف" value={vr.violationTypeLabel} testId="violation-type" />
          <ReadonlyRow label="شرح تخلف" value={vr.description} testId="violation-description" />
          {vr.meetingAt && (
            <>
              <ReadonlyRow
                label="زمان جلسه"
                value={fmtMeetingDateTime(vr.meetingAt)}
                testId="violation-meeting-at"
              />
              <ReadonlyRow
                label="نحوه برگزاری"
                value={meetingModeLabel(vr.meetingMode)}
                testId="violation-meeting-mode"
              />
              <ReadonlyRow label="لینک" value={vr.meetingLink} testId="violation-meeting-link" />
              <ReadonlyRow label="محل" value={vr.meetingLocation} testId="violation-meeting-location" />
            </>
          )}
          {vr.verdictLabel && (
            <ReadonlyRow label="حکم صادره" value={vr.verdictLabel} testId="violation-verdict" />
          )}
          {vr.compensatoryConditions && (
            <ReadonlyRow
              label="شروط جبرانی"
              value={vr.compensatoryConditions}
              testId="violation-compensatory"
            />
          )}
          {vr.educationMeetingAt && (
            <ReadonlyRow
              label="جلسه کمیته آموزش"
              value={fmtMeetingDateTime(vr.educationMeetingAt)}
              testId="violation-edu-meeting"
            />
          )}
        </div>

        {(currentState === 'suspension_next_term' || currentState === 'suspension_immediate') && (
          <div
            data-testid="violation-suspension-effects"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fff7ed',
              borderRight: '4px solid #ea580c',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#9a3412',
            }}
          >
            <strong>اثرات سیستمی تعلیق:</strong>
            {' '}
            {currentState === 'suspension_immediate'
              ? 'قفل حضور در دروس ترم جاری و سوپرویژن؛ غیبت خودکار.'
              : 'قفل ثبت‌نام ترم بعد و حضور سوپرویژن فردی.'}
          </div>
        )}

        {currentState === 'expelled' && (
          <div
            data-testid="violation-expelled-notice"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.84rem',
              color: '#991b1b',
            }}
          >
            پورتال دانشجو مسدود (فقط‌خواندنی) است.
          </div>
        )}

        <StudentPerformanceLogTable log={performanceLog} compact={compact} />
      </div>
    </div>
  )
}
