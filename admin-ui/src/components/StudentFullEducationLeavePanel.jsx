import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  FullLeaveFlowStepper,
  FULL_LEAVE_STATE_HINTS,
  FULL_LEAVE_SOP_WARNING_FA,
  HintBlock,
  InfoTile,
  ScheduleChip,
  resolveFullLeaveContext,
  isFullLeaveTerminal,
  isFullLeaveActiveLeave,
  fmtIsoDate,
  fmtMeetingDateTime,
  meetingModeLabel,
} from '../utils/fullEducationLeaveDisplay'

const PROCESS_TITLE_FA = 'مرخصی موقت از کل آموزش (فرایند ۵۹)'

/**
 * داشبورد راهنمای فرایند ۵۹ — مرخصی موقت از کل آموزش.
 */
export default function StudentFullEducationLeavePanel({
  detail = null,
  active = true,
  compact = false,
  onStartReturn = null,
  canStartReturn = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const leave = useMemo(() => resolveFullLeaveContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'full_education_leave') {
    return null
  }

  const isTerminal = isFullLeaveTerminal(currentState)
  const isOnLeave = isFullLeaveActiveLeave(currentState)
  const hint = FULL_LEAVE_STATE_HINTS[currentState]
    || 'مراحل مرخصی از کل آموزش را طبق راهنمای این پنل پیش ببرید.'

  const showMeeting = [
    'session_scheduled',
    'committee_decision',
    'therapist_assignment',
    'on_leave',
    'return_reminder_sent',
  ].includes(currentState) && leave.meetingAt

  const showSopWarning = currentState === 'leave_request'
  const showTherapyCoord = currentState === 'therapist_assignment' && leave.hasActiveTherapist
  const showRejected = currentState === 'leave_rejected' && leave.rejectionReason

  return (
    <div
      className="card"
      data-testid="student-full-education-leave-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : isOnLeave ? 'badge-warning' : 'badge-info'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <FullLeaveFlowStepper currentState={currentState} compact={compact} />

        {showSopWarning && (
          <HintBlock tone="#dc2626" bg="#fef2f2">
            {FULL_LEAVE_SOP_WARNING_FA}
          </HintBlock>
        )}

        {leave.internWarning && currentState === 'leave_request' && (
          <HintBlock tone="#d97706" bg="#fffbeb">
            با توجه به وضعیت انترنی، مرخصی از کل آموزش منجر به توقف سوپرویژن و ارجاع بیماران می‌شود.
          </HintBlock>
        )}

        {!isTerminal && (
          <HintBlock tone={isOnLeave ? '#d97706' : '#2563eb'} bg={isOnLeave ? '#fffbeb' : '#eff6ff'}>
            {hint}
          </HintBlock>
        )}

        {currentState === 'leave_complete' && (
          <HintBlock tone="#16a34a" bg="#f0fdf4">
            بازگشت به کل آموزش با موفقیت انجام شد.
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
          {leave.leaveTermsLabel && leave.leaveTermsLabel !== '—' && (
            <InfoTile label="مدت مرخصی" value={leave.leaveTermsLabel} tone="#0d9488" bg="#f0fdfa" />
          )}
          <InfoTile label="وضعیت بالینی" value={leave.isInternLabel} tone="#7c3aed" bg="#f5f3ff" />
          {leave.therapistName && leave.therapistName !== '—' && (
            <InfoTile label="درمانگر فعلی" value={leave.therapistName} tone="#2563eb" bg="#eff6ff" />
          )}
        </div>

        {showMeeting && (
          <div
            data-testid="full-leave-meeting-summary"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%)',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#1e3a8a' }}>جلسه کمیته پیشرفت</div>
            <div>
              <strong>زمان:</strong> {fmtMeetingDateTime(leave.meetingAt)}
              {meetingModeLabel(leave.meetingMode) ? ` · ${meetingModeLabel(leave.meetingMode)}` : ''}
            </div>
            {leave.meetingMode === 'online' && leave.meetingLink && (
              <div>
                <a href={leave.meetingLink} target="_blank" rel="noopener noreferrer">لینک جلسه</a>
              </div>
            )}
            {leave.meetingMode === 'in_person' && leave.meetingLocation && (
              <div><strong>محل:</strong> {leave.meetingLocation}</div>
            )}
          </div>
        )}

        {showTherapyCoord && (
          <div
            data-testid="full-leave-therapy-coord"
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
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#92400e' }}>تماس با مسئول هماهنگی‌ها</div>
            <p style={{ margin: 0 }}>
              {leave.therapyCoordSms || (
                <>
                  برای ادامه درمان در قالب درمان عموم، ظرف ۳ روز با مسئول هماهنگی‌ها تماس بگیرید.
                </>
              )}
            </p>
            <p style={{ margin: '0.5rem 0 0', fontWeight: 700 }}>تلفن: {leave.therapyCoordPhone}</p>
          </div>
        )}

        {showRejected && (
          <div
            data-testid="full-leave-rejected"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#991b1b' }}>شرح توافقات / علت رد</div>
            <p style={{ margin: 0, color: '#7f1d1d' }}>{leave.rejectionReason}</p>
          </div>
        )}

        {(isOnLeave || currentState === 'return_reminder_sent') && (leave.returnReminderAt || leave.returnDeadlineAt) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.55rem',
              marginBottom: '0.85rem',
            }}
          >
            {leave.returnReminderAt && (
              <ScheduleChip label="یادآوری بازگشت" value={fmtIsoDate(leave.returnReminderAt)} tone="#d97706" bg="#fffbeb" />
            )}
            {leave.returnDeadlineAt && (
              <ScheduleChip label="مهلت بازگشت" value={fmtIsoDate(leave.returnDeadlineAt)} tone="#dc2626" bg="#fef2f2" />
            )}
          </div>
        )}

        {isOnLeave && canStartReturn && onStartReturn && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            data-testid="start-return-from-full-leave-panel"
            onClick={onStartReturn}
          >
            شروع بازگشت به کل آموزش (فرایند ۶۰)
          </button>
        )}
      </div>
    </div>
  )
}
