/** نمایش مشترک زنجیره «ثبت‌نام دوره جامع» — فرایند ۳۵. */

import React from 'react'
import {
  ScheduleChip,
  fmtIsoDate,
  fmtRialAsToman,
  resolveInterviewSchedule,
} from './introductoryCourseRegistrationDisplay'

export { ScheduleChip, fmtIsoDate, fmtRialAsToman, resolveInterviewSchedule }

/** مراحل اصلی (milestone) فرایند ثبت‌نام دوره جامع. */
export const COMP_REG_FLOW_STEPS = [
  { key: 'application', label: 'ثبت درخواست', states: ['application_submitted'] },
  {
    key: 'committee',
    label: 'بررسی کمیته‌ها',
    states: ['supervision_committee_review', 'executive_review', 'scientific_review'],
  },
  { key: 'document', label: 'گزارش تجربه شخصی', states: ['document_upload'] },
  {
    key: 'interview_book',
    label: 'زمان‌بندی و پرداخت مصاحبه',
    states: ['interview_scheduled', 'interview_payment'],
  },
  {
    key: 'interview_result',
    label: 'مصاحبه و نتیجه',
    states: ['interview_completed', 'result_accepted'],
  },
  {
    key: 'registration',
    label: 'دروس و پرداخت شهریه',
    states: ['course_display', 'payment'],
  },
  { key: 'complete', label: 'ثبت‌نام نهایی', states: ['registration_complete'] },
]

export const COMP_REG_TERMINAL_REJECTS = new Set([
  'supervision_rejected',
  'scientific_rejected',
  'result_rejected',
  'result_rejected_with_suggestion',
])

/** پیام رد برای هر وضعیت ترمینال. */
export const COMP_REG_REJECT_MESSAGES = {
  supervision_rejected:
    'پروندهٔ شما توسط کمیته نظارت رد شد. برای پیگیری از طریق تیکت با بخش پذیرش تماس بگیرید.',
  scientific_rejected:
    'پروندهٔ شما توسط مسئول علمی کمیته پیشرفت رد شد. برای پیگیری از طریق تیکت با بخش پذیرش تماس بگیرید.',
  result_rejected:
    'نتیجهٔ مصاحبه: رد قطعی. برای پیگیری از طریق تیکت با بخش پذیرش تماس بگیرید.',
  result_rejected_with_suggestion:
    'نتیجهٔ مصاحبه: رد همراه با پیشنهاد. جزئیات پیشنهاد از طریق بخش پذیرش اعلام می‌شود؛ برای پیگیری تیکت ثبت کنید.',
}

/** برچسب فارسی هر وضعیت فرایند ۳۵. */
export const COMP_REG_STATE_LABELS = {
  application_submitted: 'ثبت درخواست ورود به دوره جامع',
  supervision_committee_review: 'بررسی پرونده توسط کمیته نظارت',
  supervision_rejected: 'رد توسط کمیته نظارت',
  executive_review: 'بررسی پرونده و معدل توسط مسئول اجرایی کمیته پیشرفت',
  scientific_review: 'تصمیم‌گیری مسئول علمی کمیته پیشرفت',
  scientific_rejected: 'رد توسط مسئول علمی کمیته پیشرفت',
  document_upload: 'بارگذاری گزارش تجربه شخصی',
  interview_scheduled: 'انتخاب زمان مصاحبه',
  interview_payment: 'پرداخت هزینه مصاحبه',
  interview_completed: 'مصاحبه انجام شده — در انتظار نتیجه',
  result_accepted: 'پذیرفته شده',
  result_rejected: 'رد قطعی',
  result_rejected_with_suggestion: 'رد همراه با پیشنهاد',
  course_display: 'نمایش دروس ترم ۳ (اول جامع)',
  payment: 'پرداخت شهریه (نقدی یا اقساط)',
  registration_complete: 'ثبت‌نام نهایی انجام شد',
}

export function labelCompRegState(state) {
  if (!state) return '—'
  return COMP_REG_STATE_LABELS[state] || state
}

export function isCompRegRejected(state) {
  return COMP_REG_TERMINAL_REJECTS.has(state)
}

/** شاخص مرحلهٔ فعال در stepper بر اساس وضعیت جاری. */
export function activeCompRegStepIndex(currentState) {
  if (!currentState) return 0
  if (isCompRegRejected(currentState)) return -1
  const idx = COMP_REG_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function CompRegFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeCompRegStepIndex(currentState)
  const rejected = isCompRegRejected(currentState)
  const completed = currentState === 'registration_complete'

  if (rejected) {
    const rejectMsg = COMP_REG_REJECT_MESSAGES[currentState]
      ?? 'درخواست پذیرش رد شد — برای پیگیری از طریق تیکت با بخش پذیرش تماس بگیرید.'
    return (
      <div
        data-testid="comp-reg-flow-rejected"
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
        {rejectMsg}
      </div>
    )
  }

  return (
    <div
      data-testid="comp-reg-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {COMP_REG_FLOW_STEPS.map((step, i) => {
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
            {completed && i === COMP_REG_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
