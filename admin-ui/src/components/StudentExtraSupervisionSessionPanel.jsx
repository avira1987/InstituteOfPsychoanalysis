import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import OnlineMeetingJoinCta from './OnlineMeetingJoinCta'
import {
  ExtraSupervisionFlowStepper,
  ScheduleChip,
  resolveStudentRequestedSchedule,
  resolveSupervisorAlternativeSchedule,
  resolveAgreedSchedule,
  resolveStudentCounterSchedule,
  fmtToman,
  fmtIsoDate,
} from '../utils/extraSupervisionSessionDisplay'

const PROCESS_TITLE_FA =
  'درخواست برگزاری جلسه اضافی سوپرویژن (فرایند ۲۲)'

const STATE_HINTS = {
  extra_request: {
    student: 'تاریخ و ساعت جلسهٔ اضافی را در فرم زیر وارد کنید؛ پس از «ثبت فرم»، «ادامه و ثبت مرحله» را بزنید تا درخواست به سوپروایزر برود.',
    supervisor: 'دانشجو در حال ثبت زمان پیشنهادی است.',
  },
  supervisor_review: {
    student: 'سوپروایزر در حال بررسی زمان پیشنهادی شماست. پس از اعلام نتیجه همین صفحه را تازه کنید.',
    supervisor: 'زمان پیشنهادی دانشجو را بررسی کنید؛ تأیید، پیشنهاد جایگزین، یا اعلام عدم امکان.',
  },
  student_response: {
    student: 'سوپروایزر زمان دیگری پیشنهاد داده است. اگر موافقید «تأیید» را بزنید؛ در غیر این صورت تاریخ و ساعت جدید را در فرم بنویسید.',
    supervisor: 'منتظر پاسخ دانشجو به پیشنهاد جایگزین.',
  },
  payment_required: {
    student: 'زمان جلسه تأیید شد. از بخش پرداخت همین صفحه مبلغ جلسهٔ اضافی را بپردازید؛ پس از تأیید بانک، جلسه ثبت می‌شود.',
    supervisor: 'منتظر پرداخت دانشجو برای ثبت نهایی جلسه.',
  },
  extra_session_confirmed: {
    student: 'جلسه ثبت شد. لینک ورود در همین صفحه یا پیامک ارسال می‌شود؛ در زمان مقرر حاضر شوید.',
    supervisor: 'جلسه در سیستم ثبت شد. پس از برگزاری، دکمهٔ «جلسه برگزار شد» را بزنید.',
  },
  extra_session_completed: {
    student: 'جلسهٔ اضافی برگزار شد و ساعت آن به پروندهٔ سوپرویژن شما اضافه می‌شود.',
    supervisor: 'جلسه برگزار شد و ساعت به فرایند ۵۰ ساعته متصل شد.',
  },
  extra_request_rejected: {
    student: 'سوپروایزر در حال حاضر امکان برگزاری جلسهٔ اضافی را اعلام نکرده است؛ در صورت نیاز بعداً می‌توانید دوباره درخواست دهید.',
    supervisor: 'درخواست رد شد — دانشجو می‌تواند بعداً دوباره درخواست دهد.',
  },
}

function PaymentTile({ amountRial, invoiceToman }) {
  const toman = invoiceToman != null
    ? Number(invoiceToman)
    : amountRial != null
      ? Math.round(Number(amountRial) / 10)
      : null
  if (toman == null || !Number.isFinite(toman)) return null
  return (
    <div
      data-testid="extra-supervision-payment-tile"
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: '#fffbeb',
        borderRight: '4px solid #d97706',
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>حق‌الزحمه جلسه اضافی</div>
      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#b45309' }}>{fmtToman(toman)}</div>
    </div>
  )
}

/**
 * داشبورد راهنمای «جلسه اضافی سوپرویژن» — فرایند ۲۲.
 * نمای دانشجو (پیش‌فرض) یا سوپروایزر با prop `portalRole`.
 */
export default function StudentExtraSupervisionSessionPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
  portalRole = 'student',
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const isSupervisor = portalRole === 'supervisor' || portalRole === 'admin'

  const requested = useMemo(
    () => resolveStudentRequestedSchedule(ctx, stepFormValues),
    [ctx, stepFormValues],
  )
  const alternative = useMemo(() => resolveSupervisorAlternativeSchedule(ctx), [ctx])
  const agreed = useMemo(() => resolveAgreedSchedule(ctx), [ctx])
  const counter = useMemo(
    () => resolveStudentCounterSchedule(ctx, stepFormValues),
    [ctx, stepFormValues],
  )

  const hasAlternative = !!(alternative.date || alternative.time)
  const showCounterPreview = currentState === 'student_response'
    && (counter.date || counter.time)
  const showAgreed = ['payment_required', 'extra_session_confirmed', 'extra_session_completed']
    .includes(currentState)
    && (agreed.date || agreed.time)

  const meetingLink = (
    ctx.meeting_link
    || ctx.last_session_link
    || ctx.session_link
    || ''
  ).trim()

  if (!active || !detail || detail.process_code !== 'extra_supervision_session') {
    return null
  }

  const hint = STATE_HINTS[currentState]?.[isSupervisor ? 'supervisor' : 'student']
    ?? (isSupervisor
      ? 'پروندهٔ جلسه اضافی سوپرویژن.'
      : 'جلسهٔ تکمیلی در یک هفتهٔ مشخص — پس از توافق سوپروایزر و پرداخت، در سیستم ثبت می‌شود.')

  const isTerminal = currentState === 'extra_session_completed'
    || currentState === 'extra_request_rejected'

  return (
    <div className="card" data-testid="student-extra-supervision-session-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <ExtraSupervisionFlowStepper currentState={currentState} compact={compact} />

        {!isTerminal && hint && (
          <div
            data-testid="extra-supervision-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: isSupervisor ? '#f0fdfa' : '#eff6ff',
              borderRight: `4px solid ${isSupervisor ? '#0d9488' : '#2563eb'}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: isSupervisor ? '#134e4a' : '#1e3a8a',
            }}
          >
            {hint}
          </div>
        )}

        {currentState === 'payment_required' && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            <PaymentTile
              amountRial={ctx.payment_amount_rial}
              invoiceToman={ctx.invoice_amount}
            />
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.5rem' : '0.75rem',
          }}
        >
          <ScheduleChip
            testId="extra-supervision-requested-schedule"
            label={isSupervisor ? 'زمان درخواستی دانشجو' : 'زمان درخواستی شما'}
            date={requested.date}
            time={requested.time}
            tone="#2563eb"
            bg="#eff6ff"
          />

          {hasAlternative && (
            <ScheduleChip
              testId="extra-supervision-alternative-schedule"
              label="پیشنهاد جایگزین سوپروایزر"
              date={alternative.date}
              time={alternative.time}
              tone="#d97706"
              bg="#fffbeb"
            />
          )}

          {showAgreed && (
            <ScheduleChip
              testId="extra-supervision-agreed-schedule"
              label="زمان توافق‌شده"
              date={agreed.date}
              time={agreed.time}
              tone="#16a34a"
              bg="#f0fdf4"
            />
          )}

          {showCounterPreview && (
            <ScheduleChip
              testId="extra-supervision-counter-schedule"
              label="زمان جدید (پیش‌نمایش)"
              date={counter.date}
              time={counter.time}
              tone="#ea580c"
              bg="#fff7ed"
            />
          )}
        </div>

        {currentState === 'student_response' && hasAlternative && !isSupervisor && (
          <div
            role="status"
            data-testid="extra-supervision-negotiation-note"
            style={{
              marginBottom: '0.65rem',
              padding: '0.7rem 0.9rem',
              borderRadius: '8px',
              background: '#fefce8',
              borderRight: '4px solid #ca8a04',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#713f12',
            }}
          >
            مذاکرهٔ زمانی: اگر با پیشنهاد سوپروایزر موافقید دکمهٔ تأیید را بزنید؛
            در غیر این صورت تاریخ و ساعت جدید را در فرم پایین وارد کنید.
          </div>
        )}

        {currentState === 'supervisor_review' && isSupervisor && (
          <div
            role="status"
            data-testid="extra-supervision-supervisor-review-note"
            style={{
              fontSize: '0.8rem',
              color: '#64748b',
              lineHeight: 1.65,
              margin: '0 0 0.65rem',
            }}
          >
            پس از تأیید، دانشجو به مرحلهٔ پرداخت هدایت می‌شود.
            برای «پیشنهاد جایگزین»، تاریخ و ساعت را در بخش تصمیم پایین وارد کنید.
          </div>
        )}

        {(currentState === 'extra_session_confirmed' || currentState === 'extra_session_completed') && (
          <div
            data-testid="extra-supervision-confirmed-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: '0 0 0.5rem', fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              جلسهٔ اضافی سوپرویژن ثبت شد
              {agreed.date ? ` — ${fmtIsoDate(agreed.date)}` : ''}
              {agreed.time ? ` ساعت ${agreed.time}` : ''}
              .
              {' '}
              ساعات مطابق فرایند تکمیل ۵۰ ساعته ثبت می‌شود.
            </p>
            {meetingLink && !isSupervisor && (
              <OnlineMeetingJoinCta
                meetingLink={meetingLink}
                startsAt={agreed.startsAt || ctx.session_starts_at_iso}
                meetingLinkOpenAt={ctx.meeting_link_open_at}
                meetingLinkIsVisible={ctx.meeting_link_is_visible !== false}
                compact={compact}
              />
            )}
          </div>
        )}

        {(requested.note || '').trim() && (
          <p style={{ margin: '0.65rem 0 0', fontSize: '0.82rem', color: '#57534e', lineHeight: 1.65 }}>
            <strong>توضیح دانشجو:</strong>
            {' '}
            {requested.note.trim()}
          </p>
        )}
      </div>
    </div>
  )
}
