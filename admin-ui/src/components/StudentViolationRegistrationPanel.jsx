import React, { useMemo } from 'react'
import {
  ViolationFlowStepper,
  labelViolationState,
  resolveViolationContext,
  fmtMeetingDateTime,
  meetingModeLabel,
  StudentPerformanceLogTable,
} from '../utils/violationRegistrationDisplay'

const PROCESS_TITLE_FA = 'ثبت تخلفات (فرایند ۵۵)'

const STATE_HINTS = {
  violation_reported:
    'گزارش تخلف شما ثبت شده و در حال بررسی کمیته نظارت است. در صورت نیاز با شما تماس گرفته می‌شود.',
  review_status_set: 'پرونده در حال بررسی است. در صورت نیاز به جلسه، دعوت‌نامه ارسال خواهد شد.',
  meeting_scheduled:
    'زمان جلسه کمیته نظارت در باکس زیر نمایش داده می‌شود؛ در روز مقرر طبق اعلام کمیته حاضر شوید.',
  verdict_issued:
    'حکم صادر شده در جدول گزارش عملکرد و خلاصهٔ زیر قابل مشاهده است. شروط جبرانی را رعایت کنید.',
  suspension_next_term:
    'تعلیق از ترم بعد برای شما اعمال شده است. ثبت‌نام ترم آینده تا اعلام کمیته مسدود است.',
  suspension_immediate:
    'تعلیق آنی اعمال شده است. حضور در کلاس‌ها و سوپرویژن تا اعلام کمیته محدود است.',
  referred_to_education_committee:
    'پرونده به کمیته آموزش ارجاع شده است. دعوت‌نامهٔ جلسه آنلاین ارسال می‌شود.',
  closed: 'پرونده مختومه شد.',
  expelled: 'حکم اخراج صادر شده است. پورتال شما به حالت فقط‌خواندنی درآمده است.',
}

/**
 * داشبورد راهنمای «ثبت تخلفات» — فرایند ۵۵ (دانشجو).
 */
export default function StudentViolationRegistrationPanel({
  detail = null,
  extraData = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const vr = useMemo(() => resolveViolationContext(ctx), [ctx])

  const performanceLog = useMemo(() => {
    const log = extraData?.monitoring_performance_log
    return Array.isArray(log) ? log : []
  }, [extraData])

  if (!active || !detail || detail.process_code !== 'violation_registration') {
    return null
  }

  const hint = STATE_HINTS[currentState]
    ?? 'پروندهٔ تخلف آموزشی — در صورت نیاز به اقدام، راهنمای این صفحه را دنبال کنید.'
  const isTerminal = currentState === 'closed' || currentState === 'expelled'
  const showMeeting = currentState === 'meeting_scheduled' && vr.meetingAt

  return (
    <div className="card" data-testid="student-violation-registration-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelViolationState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ViolationFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <div
            data-testid="violation-student-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: isTerminal && currentState === 'expelled' ? '#fef2f2' : '#eff6ff',
              borderRight: `4px solid ${currentState === 'expelled' ? '#dc2626' : '#2563eb'}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            {hint}
          </div>
        )}

        {showMeeting && (
          <div
            data-testid="violation-student-meeting"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.84rem',
              lineHeight: 1.75,
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>دعوت به جلسه کمیته نظارت</strong>
            <div>زمان: {fmtMeetingDateTime(vr.meetingAt)}</div>
            <div>نحوه: {meetingModeLabel(vr.meetingMode)}</div>
            {vr.meetingLink && (
              <div>
                لینک:
                {' '}
                <a href={vr.meetingLink} target="_blank" rel="noreferrer">{vr.meetingLink}</a>
              </div>
            )}
            {vr.meetingLocation && <div>محل: {vr.meetingLocation}</div>}
          </div>
        )}

        {vr.verdictLabel && ['verdict_issued', 'suspension_next_term', 'suspension_immediate', 'closed', 'expelled'].includes(currentState) && (
          <div
            data-testid="violation-student-verdict"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.75,
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>حکم صادره</strong>
            <div>{vr.verdictLabel}</div>
            {vr.compensatoryConditions && (
              <div style={{ marginTop: '0.35rem' }}>
                <strong>شروط جبرانی:</strong>
                {' '}
                {vr.compensatoryConditions}
              </div>
            )}
          </div>
        )}

        <StudentPerformanceLogTable log={performanceLog} compact={compact} />
      </div>
    </div>
  )
}
