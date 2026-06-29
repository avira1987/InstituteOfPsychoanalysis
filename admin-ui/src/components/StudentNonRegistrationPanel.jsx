import React, { useMemo } from 'react'
import {
  NonRegistrationFlowStepper,
  labelNonRegState,
  resolveNonRegistrationContext,
  computeBranchSlaRemaining,
  fmtMeetingDateTime,
  meetingModeLabel,
  BRANCH_REGISTER_SLA_DAYS,
  BRANCH_LEAVE_SLA_DAYS,
} from '../utils/studentNonRegistrationDisplay'
import { SlaBanner } from '../utils/earlyTerminationChainDisplay'

const PROCESS_TITLE_FA = 'عدم ثبت‌نام برای ترم بعد (فرایند ۴۲)'

const STATE_HINTS = {
  meeting_scheduled: 'زمان جلسه کمیته نظارت در باکس زیر نمایش داده می‌شود؛ در روز مقرر طبق اعلام کمیته حاضر شوید.',
  meeting_held: 'جلسه کمیته برگزار شده یا در حال برگزاری است. نتیجهٔ نهایی از طریق کمیته اعلام می‌شود؛ در صورت نیاز به اقدام، پیامک دریافت خواهید کرد.',
  branch_register: 'حداکثر ۲ روز فرصت دارید دروس این ترم را اخذ و شهریه را پرداخت کنید. از دکمه‌های زیر به ثبت‌نام ترم بروید.',
  branch_leave: 'حداکثر ۳ روز فرصت دارید یکی از فرایندهای مرخصی را آغاز کنید. در غیر این صورت فرایند انصراف از آموزش اجرا می‌شود.',
  branch_withdrawal: 'بر اساس تصمیم جلسه کمیته، فرایند انصراف از آموزش برای شما آغاز شده است.',
  registration_completed: 'ثبت‌نام شما در این ترم انجام شد. غیبت جلسات گذشته طبق SOP در سیستم ثبت می‌شود.',
  leave_started: 'یکی از فرایندهای مرخصی/وقفه را آغاز کردید. مراحل همان فرایند را در پنل خود دنبال کنید.',
  withdrawal_triggered: 'فرایند انصراف از آموزش اجرا شده است. در صورت پرسش با کمیته پیشرفت یا نظارت تماس بگیرید.',
}

/**
 * داشبورد راهنمای «عدم ثبت‌نام ترم بعد» — فرایند ۴۲ (دانشجو).
 */
export default function StudentNonRegistrationPanel({
  detail = null,
  activeProcesses = [],
  active = true,
  compact = false,
  onStartLeave = null,
  onStartFullLeave = null,
  onGoToRegistration = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const nr = useMemo(() => resolveNonRegistrationContext(ctx), [ctx])

  const registerSla = useMemo(
    () => (currentState === 'branch_register' ? computeBranchSlaRemaining(ctx, 'register') : null),
    [currentState, ctx],
  )
  const leaveSla = useMemo(
    () => (currentState === 'branch_leave' ? computeBranchSlaRemaining(ctx, 'leave') : null),
    [currentState, ctx],
  )

  if (!active || !detail || detail.process_code !== 'student_non_registration') {
    return null
  }

  const hint = STATE_HINTS[currentState]
    ?? 'پروندهٔ عدم ثبت‌نام ترم — در صورت نیاز به اقدام، راهنمای این صفحه را دنبال کنید.'
  const isTerminal = [
    'branch_withdrawal',
    'registration_completed',
    'leave_started',
    'withdrawal_triggered',
  ].includes(currentState)

  const regProcess = (activeProcesses || []).find(
    (p) => !p.is_completed && !p.is_cancelled
      && ['comprehensive_term_start', 'intro_second_semester_registration'].includes(p.process_code),
  )

  const showMeeting = ['meeting_scheduled', 'meeting_held'].includes(currentState) && nr.meetingAt

  return (
    <div className="card" data-testid="student-non-registration-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelNonRegState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <NonRegistrationFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <div
            data-testid="non-reg-student-hint"
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
            {hint}
          </div>
        )}

        {nr.termCode && (
          <p style={{ fontSize: '0.82rem', margin: '0 0 0.75rem', color: '#64748b' }}>
            ترم:
            {' '}
            <strong>{nr.termCode}</strong>
          </p>
        )}

        {showMeeting && (
          <div
            data-testid="non-reg-student-meeting"
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
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#1e3a8a' }}>
              جلسه کمیته نظارت
            </div>
            <div>
              <strong>زمان:</strong>
              {' '}
              {fmtMeetingDateTime(nr.meetingAt)}
              {meetingModeLabel(nr.meetingMode) ? ` · ${meetingModeLabel(nr.meetingMode)}` : ''}
            </div>
            {nr.meetingMode === 'online' && nr.meetingLink && (
              <div style={{ marginTop: '0.35rem' }}>
                <a href={nr.meetingLink} target="_blank" rel="noopener noreferrer">
                  لینک جلسه
                </a>
              </div>
            )}
            {nr.meetingMode === 'in_person' && nr.meetingLocation && (
              <div style={{ marginTop: '0.35rem' }}>
                <strong>محل:</strong>
                {' '}
                {nr.meetingLocation}
              </div>
            )}
          </div>
        )}

        {currentState === 'branch_register' && (
          <>
            <SlaBanner
              slaInfo={registerSla}
              title={`مهلت ثبت‌نام (${BRANCH_REGISTER_SLA_DAYS.toLocaleString('fa-IR')} روز)`}
              fallbackText="پس از تصمیم کمیته، حداکثر ۲ روز برای اخذ دروس و پرداخت شهریه فرصت دارید."
            />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
              {regProcess && onGoToRegistration && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  data-testid="non-reg-go-registration"
                  onClick={() => onGoToRegistration(regProcess)}
                >
                  ادامهٔ ثبت‌نام ترم
                </button>
              )}
              {!regProcess && (
                <p className="muted" style={{ margin: 0, fontSize: '0.82rem' }}>
                  اگر فرایند ثبت‌نام ترم در لیست فرایندهای شما نیست، چند دقیقه صبر کنید یا با پذیرش تماس بگیرید.
                </p>
              )}
            </div>
          </>
        )}

        {currentState === 'branch_leave' && (
          <>
            <SlaBanner
              slaInfo={leaveSla}
              title={`مهلت آغاز مرخصی (${BRANCH_LEAVE_SLA_DAYS.toLocaleString('fa-IR')} روز)`}
              fallbackText="حداکثر ۳ روز برای شروع یکی از فرایندهای مرخصی فرصت دارید."
            />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
              {onStartLeave && (
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  data-testid="non-reg-start-educational-leave"
                  onClick={() => onStartLeave()}
                >
                  مرخصی آموزشی (از ثبت‌نام کلاس)
                </button>
              )}
              {onStartFullLeave && (
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  data-testid="non-reg-start-full-leave"
                  onClick={() => onStartFullLeave()}
                >
                  مرخصی از کل آموزش
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
