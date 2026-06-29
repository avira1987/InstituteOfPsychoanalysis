import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  FullLeaveFlowStepper,
  HintBlock,
  InfoTile,
  resolveFullLeaveContext,
  fmtMeetingDateTime,
  meetingModeLabel,
} from '../utils/fullEducationLeaveDisplay'

const PROCESS_TITLE_FA = 'بررسی مرخصی از کل آموزش (فرایند ۵۹)'

const STATE_HINTS = {
  committee_review: 'پرونده را بررسی و ظرف ۷ روز تاریخ، ساعت و نحوهٔ برگزاری جلسه را در فرم ثبت کنید.',
  deputy_alerted: 'مهلت ۷ روزه ثبت جلسه گذشته است. لطفاً فوراً جلسه را تعیین و ثبت کنید.',
  session_scheduled: 'جلسه ثبت شده است. پس از برگزاری، دکمهٔ «برگزاری جلسه» و سپس تأیید/رد را بزنید.',
  committee_decision: 'پس از جلسه، فرم «ثبت نتیجهٔ نهایی» را تکمیل کنید و تأیید یا رد را ثبت کنید.',
}

/**
 * پنل کمیته پیشرفت — فرایند ۵۹.
 */
export default function FullEducationLeaveCommitteeReviewPanel({
  detail = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const leave = useMemo(() => resolveFullLeaveContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'full_education_leave') {
    return null
  }

  const committeeStates = ['committee_review', 'deputy_alerted', 'session_scheduled', 'committee_decision']
  if (!committeeStates.includes(currentState)) {
    return null
  }

  const hint = STATE_HINTS[currentState] || 'پرونده مرخصی از کل آموزش — اقدام کمیته پیشرفت.'
  const showSla = ['committee_review', 'deputy_alerted'].includes(currentState)

  return (
    <div
      className="card"
      data-testid="full-education-leave-committee-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <FullLeaveFlowStepper currentState={currentState} compact={compact} />

        {showSla && (
          <HintBlock tone="#dc2626" bg="#fef2f2">
            مهلت ثبت جلسه: حداکثر ۷ روز از تاریخ ارسال درخواست. در صورت تأخیر، معاون مدیر آموزش مطلع می‌شود.
          </HintBlock>
        )}

        <HintBlock tone="#2563eb" bg="#eff6ff">{hint}</HintBlock>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.75rem',
          }}
        >
          <InfoTile label="مدت مرخصی درخواستی" value={leave.leaveTermsLabel} tone="#0d9488" bg="#f0fdfa" />
          <InfoTile label="وضعیت بالینی" value={leave.isInternLabel} tone="#7c3aed" bg="#f5f3ff" />
          {leave.therapistName && leave.therapistName !== '—' && (
            <InfoTile label="درمانگر فعلی" value={leave.therapistName} tone="#2563eb" bg="#eff6ff" />
          )}
        </div>

        {leave.meetingAt && currentState !== 'committee_review' && (
          <div style={{ fontSize: '0.86rem', lineHeight: 1.75, marginBottom: '0.5rem' }}>
            <strong>جلسه ثبت‌شده:</strong> {fmtMeetingDateTime(leave.meetingAt)}
            {meetingModeLabel(leave.meetingMode) ? ` · ${meetingModeLabel(leave.meetingMode)}` : ''}
          </div>
        )}
      </div>
    </div>
  )
}
