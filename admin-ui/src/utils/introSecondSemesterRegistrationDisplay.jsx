/** نمایش مشترک زنجیره «ثبت‌نام ترم دوم دوره آشنایی» — فرایند ۳۳. */

import React from 'react'
import { fmtIsoDate, fmtToman, fmtRialAsToman } from './introductoryCourseRegistrationDisplay'

export { fmtIsoDate, fmtToman, fmtRialAsToman }

/** مراحل اصلی (milestone) فرایند ثبت‌نام ترم دوم. */
export const INTRO2_FLOW_STEPS = [
  { key: 'course_selection', label: 'انتخاب دروس ترم دوم', states: ['course_selection'] },
  { key: 'payment_method', label: 'انتخاب روش پرداخت', states: ['payment_method'] },
  { key: 'payment', label: 'پرداخت', states: ['payment_processing'] },
  { key: 'complete', label: 'ثبت‌نام نهایی', states: ['registration_complete', 'installment_overdue'] },
  { key: 'closed', label: 'پایان ثبت‌نام ترم دوم', states: ['term2_registration_closed'] },
]

/** وضعیت‌های توقف (terminal با شکست صلاحیت). */
export const INTRO2_TERMINAL_STOP = new Set(['therapy_check_failed', 'suspension_check_failed'])

/** برچسب فارسی هر وضعیت فرایند ۳۳. */
export const INTRO2_STATE_LABELS = {
  eligibility_check: 'بررسی صلاحیت ثبت‌نام',
  therapy_check_failed: 'توقف — شرط درمان برآورده نشده',
  suspension_check_failed: 'توقف — دانشجو تعلیق شده',
  course_selection: 'انتخاب دروس ترم دوم',
  payment_method: 'انتخاب روش پرداخت',
  payment_processing: 'در حال پرداخت',
  registration_complete: 'ثبت‌نام نهایی انجام شد',
  installment_overdue: 'قسط معوق — بلاک حضور و غیاب',
  term2_registration_closed: 'پایان ثبت‌نام ترم دوم — تسویه مالی تکمیل‌شده',
}

/** پیام توقف برای وضعیت‌های شکست صلاحیت. */
export const INTRO2_STOP_MESSAGES = {
  therapy_check_failed: 'برای ثبت‌نام ترم دوم ابتدا باید درمان شخصی خود را آغاز و درمانگر فعال ثبت کنید.',
  suspension_check_failed: 'به دلیل تعلیق از آموزش، امکان ثبت‌نام در ترم جدید وجود ندارد.',
}

export function labelIntro2State(state) {
  if (!state) return '—'
  return INTRO2_STATE_LABELS[state] || state
}

/** شاخص مرحلهٔ فعال در stepper بر اساس وضعیت جاری. */
export function activeIntro2StepIndex(currentState) {
  if (!currentState) return 0
  if (INTRO2_TERMINAL_STOP.has(currentState)) return -1
  const idx = INTRO2_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

/** داده‌های کلیدی ترم دوم از context. */
export function resolveTerm2Context(ctx = {}) {
  return {
    admissionType: ctx.admission_type ?? ctx.result ?? null,
    paymentMethod: ctx.payment_method ?? null,
    installmentCount: ctx.installment_count ?? null,
    nextInstallmentDueAt: ctx.next_installment_due_at ?? null,
    pendingInstallmentsRemaining: ctx.pending_installments_remaining ?? null,
    tuitionToman: fmtRialAsToman(ctx.tuition_amount_rial, ctx.tuition_amount),
  }
}

/** برچسب فارسی نوع پذیرش (برای ترم دوم). */
export const ADMISSION_TYPE_LABELS_T2 = {
  conditional_therapy: 'پذیرش مشروط به درمان',
  single_course: 'پذیرش تک‌درس (فقط درس مجاز ترم دوم)',
  full_admission: 'پذیرش کامل',
}

/** برچسب فارسی روش پرداخت. */
export const PAYMENT_METHOD_LABELS = {
  cash: 'نقدی (یکجا)',
  installment: 'اقساطی',
}

export function Intro2FlowStepper({ currentState, compact = false }) {
  const activeIdx = activeIntro2StepIndex(currentState)
  const isStop = INTRO2_TERMINAL_STOP.has(currentState)
  const completed = currentState === 'term2_registration_closed'

  if (isStop) {
    return (
      <div
        data-testid="intro2-flow-stopped"
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
        {INTRO2_STOP_MESSAGES[currentState] || 'ثبت‌نام ترم دوم در این مرحله متوقف شد.'}
      </div>
    )
  }

  return (
    <div
      data-testid="intro2-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {INTRO2_FLOW_STEPS.map((step, i) => {
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
            {completed && i === INTRO2_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
