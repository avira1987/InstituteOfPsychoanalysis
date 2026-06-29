/** نمایش مشترک زنجیره «آغاز ترم‌های دوره جامع» — فرایند ۴۰. */

import React from 'react'
import { fmtIsoDate, fmtRialAsToman } from './introductoryCourseRegistrationDisplay'

export { fmtIsoDate, fmtRialAsToman }

/** مراحل اصلی (milestone) فرایند آغاز ترم دوره جامع. */
export const COMP_TERM_START_FLOW_STEPS = [
  { key: 'course_display', label: 'دروس و شهریه', states: ['course_display'] },
  { key: 'payment_choice', label: 'انتخاب روش پرداخت', states: ['payment_choice'] },
  { key: 'payment', label: 'پرداخت', states: ['payment_processing'] },
  { key: 'complete', label: 'ثبت‌نام نهایی', states: ['registration_complete'] },
]

/** وضعیت‌های توقف (terminal با شکست صلاحیت). */
export const COMP_TERM_START_TERMINAL_STOP = new Set(['blocked'])

/** برچسب فارسی هر وضعیت فرایند ۴۰. */
export const COMP_TERM_START_STATE_LABELS = {
  eligibility_check: 'بررسی موانع (تعلیق/مرخصی)',
  blocked: 'مسدود — تعلیق یا مرخصی',
  course_display: 'نمایش دروس و شهریه',
  payment_choice: 'انتخاب نحوه پرداخت',
  payment_processing: 'در حال پرداخت',
  registration_complete: 'ثبت‌نام نهایی — لینک کلاس‌ها فعال',
}

/** پیام توقف برای وضعیت blocked (مطابق Pop-up SOP). */
export const COMP_TERM_START_STOP_MESSAGES = {
  blocked: 'امکان ثبت‌نام در ترم جدید به دلیل وضعیت فعلی پرونده شما (تعلیق انضباطی یا وضعیت مرخصی تحصیلی) وجود ندارد. در صورت نیاز به رفع این وضعیت یا بازگشت از مرخصی، با واحد انستیتو تماس حاصل فرمایید: ۰۲۱۲۲۷۲۸۰۰۰',
}

export function labelCompTermStartState(state) {
  if (!state) return '—'
  return COMP_TERM_START_STATE_LABELS[state] || state
}

/** شاخص مرحلهٔ فعال در stepper بر اساس وضعیت جاری. */
export function activeCompTermStartStepIndex(currentState) {
  if (!currentState) return 0
  if (COMP_TERM_START_TERMINAL_STOP.has(currentState)) return -1
  if (currentState === 'eligibility_check') return -2
  const idx = COMP_TERM_START_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

/**
 * داده‌های کلیدی ثبت‌نام ترم جامع از context و (اختیاری) مقادیر فرم مرحله.
 */
export function resolveCompTermContext(ctx = {}, stepFormValues = {}) {
  const paymentMethod = ctx.payment_method ?? stepFormValues.payment_method ?? null
  const installmentCount = ctx.installment_count ?? stepFormValues.installment_count ?? null
  const mandatoryCourses = Array.isArray(ctx.courses) ? ctx.courses : []
  const remedialCourses = Array.isArray(ctx.remedial_courses) ? ctx.remedial_courses : []
  const allCourses = remedialCourses.length > 0
    ? [...mandatoryCourses, ...remedialCourses]
    : mandatoryCourses

  return {
    termNumber: ctx.term_number ?? ctx.comprehensive_term_number ?? null,
    paymentMethod,
    installmentCount,
    nextInstallmentDueAt: ctx.next_installment_due_at ?? null,
    pendingInstallmentsRemaining: ctx.pending_installments_remaining ?? null,
    tuitionToman: fmtRialAsToman(ctx.tuition_amount_rial, ctx.tuition_amount),
    courses: allCourses,
    mandatoryCourses,
    remedialCourses,
    registeredAt: ctx.registered_at ?? null,
  }
}

/** برچسب فارسی روش پرداخت. */
export const PAYMENT_METHOD_LABELS = {
  cash: 'نقدی (یکجا)',
  installment: 'اقساطی',
}

export function CompTermStartFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeCompTermStartStepIndex(currentState)
  const isStop = COMP_TERM_START_TERMINAL_STOP.has(currentState)
  const completed = currentState === 'registration_complete'
  const isEligibilityPending = currentState === 'eligibility_check'

  if (isStop) {
    return (
      <div
        data-testid="comp-term-start-flow-stopped"
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
        {COMP_TERM_START_STOP_MESSAGES[currentState] || 'ثبت‌نام ترم جدید در این مرحله متوقف شد.'}
      </div>
    )
  }

  if (isEligibilityPending) {
    return (
      <div
        data-testid="comp-term-start-eligibility-pending"
        style={{
          marginBottom: compact ? '0.65rem' : '0.85rem',
          padding: '0.75rem 1rem',
          borderRadius: '10px',
          background: '#fffbeb',
          borderRight: '4px solid #d97706',
          fontSize: '0.84rem',
          lineHeight: 1.65,
          color: '#92400e',
        }}
      >
        در حال بررسی موانع ثبت‌نام (تعلیق انضباطی یا مرخصی تحصیلی)…
      </div>
    )
  }

  return (
    <div
      data-testid="comp-term-start-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {COMP_TERM_START_FLOW_STEPS.map((step, i) => {
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
              .{' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
            {completed && i === COMP_TERM_START_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
