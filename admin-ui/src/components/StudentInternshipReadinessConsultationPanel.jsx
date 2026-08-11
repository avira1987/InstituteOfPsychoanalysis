import React, { useMemo } from 'react'
import SepPaymentPanel from './SepPaymentPanel'
import {
  PROCESS_STUDENT_TASK_LABELS_FA,
  PROCESS_STATE_LABELS_FA,
} from '../utils/processMetadataLabels'
import {
  InternshipReadinessFlowStepper,
  ScheduleChip,
  labelInternshipState,
  resolveInternshipContext,
  isInternshipStopState,
  isSystemWaitState,
  fmtIsoDate,
  fmtTimeHm,
  fmtRialAsToman,
  MEETING_TYPE_LABELS,
} from '../utils/internshipReadinessConsultationDisplay'

const PROCESS_TITLE_FA = 'مشورت و تعیین آمادگی برای آغاز انترنی (فرایند ۳۷)'
const PROC_CODE = 'internship_readiness_consultation'

function resolveInternshipHint(state) {
  if (!state) return 'آغاز انترنی — مراحل را طبق راهنمای پنل پیش ببرید.'
  const task = PROCESS_STUDENT_TASK_LABELS_FA[PROC_CODE]?.[state]
  if (task) return task
  return 'آغاز انترنی — مراحل را طبق راهنمای پنل پیش ببرید.'
}

function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (value == null || value === '') return null
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '1.05rem', fontWeight: 800, color: tone }}>{value}</div>
    </div>
  )
}

const POST_INTERVIEW_STATES = [
  'interview_scheduling',
  'interview_held',
  'interview_result_unconditional',
  'interview_result_conditional',
  'contract_practice',
  'contract_rules',
  'promissory_note',
  'capacity_check',
  'pending_patient',
  'supervisor_selection',
  'first_session_payment',
  'internship_started',
]

const POST_RESULT_STATES = [
  'interview_result_unconditional',
  'interview_result_conditional',
  'contract_practice',
  'contract_rules',
  'promissory_note',
  'capacity_check',
  'pending_patient',
  'supervisor_selection',
  'first_session_payment',
  'internship_started',
]

/**
 * داشبورد راهنمای «مشورت و تعیین آمادگی برای آغاز انترنی» — فرایند ۳۷.
 */
export default function StudentInternshipReadinessConsultationPanel({
  detail = null,
  studentProfile = null,
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const internship = useMemo(() => resolveInternshipContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'internship_readiness_consultation') {
    return null
  }

  const isStop = isInternshipStopState(currentState)
  const isComplete = currentState === 'internship_started'
  const hint = resolveInternshipHint(currentState)
  const statusShort = (PROCESS_STATE_LABELS_FA[PROC_CODE]?.[currentState] || labelInternshipState(currentState)) ?? ''

  const showInterview = !!(internship.interview.date || internship.interview.time)
    && POST_INTERVIEW_STATES.includes(currentState)

  const showResult = !!internship.result.resultLabel
    && POST_RESULT_STATES.includes(currentState)

  const showWeeklyHours = Number.isFinite(internship.result.weeklyHours) && showResult
  const showSupervisor = !!(
    internship.supervisor.supervisorName
    || internship.supervisor.sessionDay
    || internship.supervisor.sessionTime
  ) && ['supervisor_selection', 'first_session_payment', 'internship_started'].includes(currentState)

  const paymentToman = fmtRialAsToman(
    ctx.payment_amount_rial,
    ctx.invoice_amount ?? ctx.session_fee_toman,
  )
  const showPaymentFee = currentState === 'first_session_payment' && paymentToman

  const meetingLabel = internship.interview.meetingType
    ? (MEETING_TYPE_LABELS[internship.interview.meetingType] || internship.interview.meetingType)
    : null

  return (
    <div className="card" data-testid="student-internship-readiness-consultation-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isStop ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelInternshipState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <InternshipReadinessFlowStepper currentState={currentState} compact={compact} />

        {!isStop && hint && (
          <div
            data-testid="internship-readiness-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#eff6ff',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#1e3a8a',
            }}
          >
            {statusShort && (
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>
                وضعیت فعلی: {statusShort}
              </div>
            )}
            <div style={{ fontWeight: 600, marginBottom: '0.2rem' }}>اقدام بعدی شما</div>
            {hint}
          </div>
        )}

        {isSystemWaitState(currentState) && (
          <p
            className="muted"
            style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', lineHeight: 1.65 }}
          >
            این مرحله توسط سامانه یا واحد مربوطه انجام می‌شود؛ در صورت تأخیر، صفحه را یک‌بار تازه کنید.
          </p>
        )}

        {currentState === 'promissory_note' && (
          <div
            data-testid="internship-promissory-reminder"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#92400e',
            }}
          >
            <strong>تحویل حضوری سفته:</strong>
            {' '}
            سفته را به صورت حضوری به انستیتو تحویل دهید. تا زمان ثبت دریافت توسط کمیته پیشرفت، مرحلهٔ بعد باز نمی‌شود.
          </div>
        )}

        {(showWeeklyHours || showPaymentFee) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {showWeeklyHours && (
              <InfoTile
                label="ساعت مجاز درمان هفتگی"
                value={`${Number(internship.result.weeklyHours).toLocaleString('fa-IR')} ساعت`}
                tone="#0d9488"
                bg="#f0fdfa"
              />
            )}
            {showPaymentFee && (
              <InfoTile label="هزینه جلسه اول سوپرویژن" value={paymentToman} tone="#b45309" bg="#fffbeb" />
            )}
          </div>
        )}

        {showInterview && (
          <div
            data-testid="internship-interview-schedule"
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.55rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            <ScheduleChip label="تاریخ مصاحبه" value={fmtIsoDate(internship.interview.date)} />
            <ScheduleChip label="ساعت مصاحبه" value={fmtTimeHm(internship.interview.time)} tone="#7c3aed" bg="#f5f3ff" />
            {meetingLabel && (
              <ScheduleChip label="نحوه برگزاری" value={meetingLabel} tone="#0d9488" bg="#f0fdfa" />
            )}
            {internship.interview.meetingType === 'online' && internship.interview.link && (
              <ScheduleChip label="لینک جلسه" value={internship.interview.link} tone="#2563eb" bg="#eff6ff" />
            )}
          </div>
        )}

        {showResult && (
          <div
            data-testid="internship-interview-result"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#166534',
            }}
          >
            <strong>نتیجه مصاحبه:</strong>
            {' '}
            {internship.result.resultLabel}
          </div>
        )}

        {showSupervisor && (
          <div
            data-testid="internship-supervisor-selection"
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.55rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {internship.supervisor.supervisorName && (
              <ScheduleChip
                label="سوپروایزر"
                value={internship.supervisor.supervisorName}
                tone="#7c3aed"
                bg="#f5f3ff"
              />
            )}
            {internship.supervisor.sessionDay && (
              <ScheduleChip label="روز جلسه" value={internship.supervisor.sessionDay} />
            )}
            {internship.supervisor.sessionTime && (
              <ScheduleChip label="ساعت جلسه" value={fmtTimeHm(internship.supervisor.sessionTime)} />
            )}
            {internship.supervisor.firstSessionDate && (
              <ScheduleChip
                label="تاریخ شروع"
                value={fmtIsoDate(internship.supervisor.firstSessionDate)}
                tone="#0d9488"
                bg="#f0fdfa"
              />
            )}
          </div>
        )}

        {currentState === 'first_session_payment' && studentProfile?.id && (
          <div style={{ marginBottom: '0.85rem' }} data-testid="internship-first-session-sep-payment">
            <SepPaymentPanel
              instanceId={detail.instance_id}
              studentId={studentProfile.id}
              amountRial={internship.paymentAmountRial > 0 ? internship.paymentAmountRial : undefined}
              description="پرداخت جلسه اول سوپرویژن (آغاز انترنی)"
            />
          </div>
        )}

        {isComplete && (
          <div
            data-testid="internship-started-complete-block"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              تبریک! انترنی شما آغاز شد. جلسات سوپرویژن در LMS ثبت شده و جزئیات از طریق پیامک اعلام می‌شود.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
