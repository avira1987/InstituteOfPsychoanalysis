import React, { useMemo } from 'react'
import {
  Intro2FlowStepper,
  labelIntro2State,
  resolveTerm2Context,
  INTRO2_TERMINAL_STOP,
  INTRO2_STOP_MESSAGES,
  ADMISSION_TYPE_LABELS_T2,
  PAYMENT_METHOD_LABELS,
  fmtIsoDate,
} from '../utils/introSecondSemesterRegistrationDisplay'

const PROCESS_TITLE_FA = 'ثبت‌نام ترم دوم دوره آشنایی (فرایند ۳۳)'

/** راهنمای هر وضعیت برای دانشجو. */
const STATE_HINTS = {
  eligibility_check: 'سامانه در حال بررسی صلاحیت ثبت‌نام شماست (شرط درمان و وضعیت تعلیق). این مرحله خودکار است؛ چند لحظه بعد صفحه را تازه کنید.',
  course_selection: 'دروس مجاز ترم دوم را بر اساس نوع پذیرش و فهرست منتشرشدهٔ آماده‌سازی ترم انتخاب و تأیید کنید.',
  payment_method: 'روش پرداخت را انتخاب کنید: نقدی (یکجا) یا اقساطی (حداکثر ۴ قسط). دانشجویان تک‌درس فقط مجاز به پرداخت نقدی هستند.',
  payment_processing: 'از بخش پرداخت سپ همین صفحه استفاده کنید. پس از بازگشت از بانک، صفحه را یک‌بار تازه کنید تا تأیید پرداخت ثبت شود؛ در صورت خطا دوباره تلاش کنید.',
  registration_complete: 'ثبت‌نام شما در ترم دوم نهایی شد و لینک کلاس آنلاین فعال است. در صورت انتخاب پرداخت اقساطی، اقساط بعدی را در سررسید پرداخت کنید.',
  installment_overdue: 'قسط معوق دارید و ثبت حضور و غیاب شما بلاک شده است. برای رفع بلاک، قسط معوق را پرداخت کنید.',
  term2_registration_closed: 'تسویه مالی کامل شد و فرایند ثبت‌نام ترم دوم بسته شد. دروس و لینک‌های کلاس در پنل آموزش در دسترس است.',
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

/**
 * داشبورد راهنمای «ثبت‌نام ترم دوم دوره آشنایی» — فرایند ۳۳.
 * نمای دانشجو با مراحل، راهنمای وضعیت، و خلاصهٔ پذیرش/پرداخت/اقساط.
 */
export default function StudentIntroSecondSemesterRegistrationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const term2 = useMemo(() => resolveTerm2Context(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'intro_second_semester_registration') {
    return null
  }

  const isStop = INTRO2_TERMINAL_STOP.has(currentState)
  const isComplete = currentState === 'registration_complete'
  const isClosed = currentState === 'term2_registration_closed'

  const hint = STATE_HINTS[currentState]
    ?? 'ثبت‌نام ترم دوم دوره آشنایی — مراحل را طبق راهنمای پنل پیش ببرید.'

  const admissionLabel = term2.admissionType
    ? (ADMISSION_TYPE_LABELS_T2[term2.admissionType] || term2.admissionType)
    : null
  const showAdmission = !!admissionLabel && [
    'course_selection', 'payment_method', 'payment_processing',
    'registration_complete', 'installment_overdue', 'term2_registration_closed',
  ].includes(currentState)

  const showTuition = ['payment_method', 'payment_processing', 'registration_complete', 'installment_overdue'].includes(currentState)
    && term2.tuitionToman

  const paymentLabel = term2.paymentMethod ? (PAYMENT_METHOD_LABELS[term2.paymentMethod] || term2.paymentMethod) : null
  const paymentValue = paymentLabel
    ? (term2.paymentMethod === 'installment' && term2.installmentCount
      ? `${paymentLabel} — ${Number(term2.installmentCount).toLocaleString('fa-IR')} قسط`
      : paymentLabel)
    : null
  const showPayment = !!paymentValue && ['payment_processing', 'registration_complete', 'installment_overdue', 'term2_registration_closed'].includes(currentState)

  const showInstallmentInfo = ['registration_complete', 'installment_overdue'].includes(currentState)
  const nextDue = showInstallmentInfo && term2.nextInstallmentDueAt ? fmtIsoDate(term2.nextInstallmentDueAt) : null
  const remaining = showInstallmentInfo && term2.pendingInstallmentsRemaining != null
    ? `${Number(term2.pendingInstallmentsRemaining).toLocaleString('fa-IR')} قسط`
    : null

  return (
    <div className="card" data-testid="student-intro-second-semester-registration-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isStop ? 'badge-danger' : (isComplete || isClosed) ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelIntro2State(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <Intro2FlowStepper currentState={currentState} compact={compact} />

        {isStop && (
          <div
            role="status"
            data-testid="intro2-stop-message"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#991b1b',
            }}
          >
            {INTRO2_STOP_MESSAGES[currentState]}
          </div>
        )}

        {!isStop && hint && (
          <div
            data-testid="intro2-state-hint"
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

        {(showAdmission || showTuition || showPayment || nextDue || remaining) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {showAdmission && (
              <InfoTile label="نوع پذیرش" value={admissionLabel} tone="#16a34a" bg="#f0fdf4" />
            )}
            {showTuition && (
              <InfoTile label="شهریه ترم" value={term2.tuitionToman} tone="#b45309" bg="#fffbeb" />
            )}
            {showPayment && (
              <InfoTile label="روش پرداخت" value={paymentValue} tone="#7c3aed" bg="#f5f3ff" />
            )}
            {nextDue && (
              <InfoTile label="سررسید قسط بعدی" value={nextDue} tone="#2563eb" bg="#eff6ff" />
            )}
            {remaining && (
              <InfoTile label="اقساط باقی‌مانده" value={remaining} tone="#2563eb" bg="#eff6ff" />
            )}
          </div>
        )}

        {currentState === 'installment_overdue' && (
          <div
            role="status"
            data-testid="intro2-overdue-note"
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#991b1b',
            }}
          >
            توجه: تا پرداخت قسط معوق، امکان ثبت حضور شما در کلاس‌ها وجود ندارد و غیبت ثبت می‌شود.
          </div>
        )}

        {(isComplete || isClosed) && (
          <div
            data-testid="intro2-complete-block"
            style={{
              marginTop: '0.5rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              {isClosed
                ? 'ثبت‌نام ترم دوم تکمیل و تسویه مالی نهایی شد. دروس و لینک‌های کلاس آنلاین در پنل آموزش در دسترس است.'
                : 'ثبت‌نام شما در ترم دوم نهایی شد و لینک کلاس آنلاین فعال است. اقساط بعدی را در سررسید پرداخت کنید.'}
              {ctx.registered_at ? ` — ${fmtIsoDate(ctx.registered_at)}` : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
