/** نمایش مشترک زنجیره «ثبت‌نام دوره آشنایی» — فرایند ۳۱. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

/** مراحل اصلی (milestone) فرایند ثبت‌نام دوره آشنایی. */
export const INTRO_REG_FLOW_STEPS = [
  { key: 'application', label: 'فرم پذیرش و انتخاب زمان مصاحبه', states: ['application_submitted', 'interview_scheduled'] },
  { key: 'interview_payment', label: 'پرداخت هزینه مصاحبه', states: ['interview_payment', 'interview_payment_confirmed'] },
  { key: 'interview', label: 'مصاحبه و ثبت نتیجه', states: ['interview_completed', 'result_conditional_therapy', 'result_single_course', 'result_full_admission'] },
  { key: 'documents', label: 'آپلود و بررسی مدارک', states: ['documents_upload', 'documents_incomplete', 'documents_review'] },
  { key: 'course_selection', label: 'حساب کاربری و انتخاب درس', states: ['credentials_created', 'course_selection'] },
  { key: 'payment', label: 'پرداخت شهریه', states: ['payment'] },
  { key: 'complete', label: 'ثبت‌نام نهایی', states: ['registration_complete', 'installment_overdue'] },
]

export const INTRO_REG_TERMINAL_REJECT = 'rejected'

/** برچسب فارسی هر وضعیت فرایند ۳۱. */
export const INTRO_REG_STATE_LABELS = {
  application_submitted: 'فرم پذیرش تکمیل شد',
  interview_scheduled: 'زمان مصاحبه انتخاب شد',
  interview_payment: 'در انتظار پرداخت هزینه مصاحبه',
  interview_payment_confirmed: 'پرداخت هزینه مصاحبه تأیید شد',
  interview_completed: 'مصاحبه انجام شد — در انتظار نتیجه',
  result_conditional_therapy: 'پذیرش مشروط به درمان',
  result_single_course: 'پذیرش تک‌درس',
  result_full_admission: 'پذیرش کامل',
  rejected: 'رد شد',
  documents_upload: 'در انتظار آپلود مدارک',
  documents_review: 'بررسی مدارک',
  documents_incomplete: 'مدارک ناقص',
  credentials_created: 'حساب کاربری ایجاد شد',
  course_selection: 'انتخاب دروس مجاز',
  payment: 'پرداخت شهریه',
  registration_complete: 'ثبت‌نام نهایی انجام شد',
  installment_overdue: 'قسط معوق — بلاک حضور و غیاب',
}

/** برچسب فارسی نوع پذیرش. */
export const ADMISSION_TYPE_LABELS = {
  conditional_therapy: 'پذیرش مشروط به شروع درمان شخصی',
  single_course: 'پذیرش تک‌درس (فقط تئوری روانکاوی همان ترم)',
  full_admission: 'پذیرش کامل (بدون شرط)',
}

export function labelIntroRegState(state) {
  if (!state) return '—'
  return INTRO_REG_STATE_LABELS[state] || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function fmtTimeHm(raw) {
  if (!raw) return '—'
  const s = String(raw).trim()
  return s || '—'
}

export function fmtToman(amount) {
  if (amount == null || amount === '') return '—'
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fa-IR')} تومان`
}

/** مبلغ ریالی را به تومان تبدیل و قالب‌بندی می‌کند. */
export function fmtRialAsToman(rial, fallbackToman) {
  const toman = fallbackToman != null
    ? Number(fallbackToman)
    : rial != null
      ? Math.round(Number(rial) / 10)
      : null
  if (toman == null || !Number.isFinite(toman)) return null
  return fmtToman(toman)
}

/** شاخص مرحلهٔ فعال در stepper بر اساس وضعیت جاری. */
export function activeIntroRegStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === INTRO_REG_TERMINAL_REJECT) return -1
  const idx = INTRO_REG_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

/** زمان مصاحبه از context. */
export function resolveInterviewSchedule(ctx = {}) {
  return {
    date: ctx.interview_date ?? ctx.interview_slot_date ?? null,
    time: ctx.interview_time ?? ctx.interview_slot_time ?? null,
    type: ctx.interview_type ?? null,
  }
}

/** نوع پذیرش و تعداد درس مجاز از context. */
export function resolveAdmission(ctx = {}) {
  return {
    type: ctx.admission_type ?? ctx.result ?? null,
    allowedCourseCount: ctx.allowed_course_count ?? ctx.allowedCourseCount ?? null,
  }
}

export function ScheduleChip({
  label, date, time, extra, tone = '#0d9488', bg = '#f0fdfa', testId,
}) {
  if (!date && !time && !extra) return null
  return (
    <div
      data-testid={testId}
      style={{
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        fontSize: '0.84rem',
        lineHeight: 1.7,
      }}
    >
      {label && (
        <div style={{ fontWeight: 700, color: tone, marginBottom: '0.35rem', fontSize: '0.82rem' }}>
          {label}
        </div>
      )}
      {(date || time) && (
        <>
          <div>
            <strong>تاریخ:</strong>
            {' '}
            {fmtIsoDate(date)}
          </div>
          <div>
            <strong>ساعت:</strong>
            {' '}
            <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtTimeHm(time)}</span>
          </div>
        </>
      )}
      {extra && <div style={{ marginTop: date || time ? '0.25rem' : 0 }}>{extra}</div>}
    </div>
  )
}

export function IntroRegFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeIntroRegStepIndex(currentState)
  const rejected = currentState === INTRO_REG_TERMINAL_REJECT
  const completed = currentState === 'registration_complete'

  if (rejected) {
    return (
      <div
        data-testid="intro-reg-flow-rejected"
        style={{
          marginBottom: compact ? '0.65rem' : '0.85rem',
          padding: '0.75rem 1rem',
          borderRadius: '10px',
          background: '#fef2f2',
          borderRight: '4px solid #dc2626',
          fontSize: '0.84rem',
          lineHeight: 1.65,
          color: '#991b1b',
        }}
      >
        درخواست پذیرش رد شد — امکان ثبت‌نام مجدد در این دوره وجود ندارد. برای پیگیری از طریق تیکت با بخش پذیرش تماس بگیرید.
      </div>
    )
  }

  return (
    <div
      data-testid="intro-reg-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {INTRO_REG_FLOW_STEPS.map((step, i) => {
        const done = completed ? true : i < activeIdx
        const current = !completed && i === activeIdx
        const tone = done ? '#16a34a' : current ? '#0d9488' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#f0fdfa' : '#f8fafc'
        return (
          <div
            key={step.key}
            style={{
              padding: compact ? '0.5rem 0.6rem' : '0.55rem 0.65rem',
              borderRadius: '8px',
              background: bg,
              borderRight: `3px solid ${tone}`,
              fontSize: compact ? '0.74rem' : '0.76rem',
              lineHeight: 1.55,
              color: done ? '#14532d' : current ? '#134e4a' : '#64748b',
            }}
          >
            <div style={{ fontWeight: 800, marginBottom: '0.15rem' }}>
              {i + 1}
              .
              {' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
            {completed && i === INTRO_REG_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
