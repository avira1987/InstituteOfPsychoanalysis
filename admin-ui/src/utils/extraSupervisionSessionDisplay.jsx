/** نمایش مشترک زنجیره «جلسه اضافی سوپرویژن» — فرایند ۲۲. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const EXTRA_SUPERVISION_FLOW_STEPS = [
  { key: 'extra_request', state: 'extra_request', label: 'ثبت درخواست' },
  { key: 'supervisor_review', state: 'supervisor_review', label: 'بررسی سوپروایزر' },
  { key: 'student_response', state: 'student_response', label: 'پاسخ به پیشنهاد' },
  { key: 'payment_required', state: 'payment_required', label: 'پرداخت' },
  { key: 'extra_session_confirmed', state: 'extra_session_confirmed', label: 'ثبت و لینک جلسه' },
  { key: 'extra_session_completed', state: 'extra_session_completed', label: 'برگزاری جلسه' },
]

export const EXTRA_SUPERVISION_TERMINAL_REJECT = 'extra_request_rejected'

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
  if (!s) return '—'
  return s
}

export function fmtToman(amount) {
  if (amount == null || amount === '') return '—'
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fa-IR')} تومان`
}

/** زمان درخواستی دانشجو — از context یا پیش‌نمایش فرم */
export function resolveStudentRequestedSchedule(ctx = {}, stepFormValues = {}) {
  const date = stepFormValues.preferred_date ?? ctx.preferred_date ?? null
  const time = stepFormValues.preferred_time ?? ctx.preferred_time ?? null
  const note = stepFormValues.request_note ?? ctx.request_note ?? null
  return { date, time, note }
}

/** پیشنهاد جایگزین سوپروایزر */
export function resolveSupervisorAlternativeSchedule(ctx = {}) {
  return {
    date: ctx.alternative_date ?? ctx.supervisor_alternative_date ?? null,
    time: ctx.alternative_time ?? ctx.supervisor_alternative_time_hhmm ?? null,
  }
}

/** زمان توافق‌شده نهایی (پس از تأیید یا پرداخت) */
export function resolveAgreedSchedule(ctx = {}) {
  return {
    date: ctx.agreed_session_date ?? ctx.confirmed_alternative_date ?? ctx.preferred_date ?? null,
    time: ctx.agreed_session_time ?? ctx.confirmed_alternative_time ?? ctx.preferred_time ?? null,
    startsAt: ctx.session_starts_at_iso ?? null,
  }
}

/** زمان جدید دانشجو در مرحلهٔ پاسخ (پیش‌نمایش فرم) */
export function resolveStudentCounterSchedule(ctx = {}, stepFormValues = {}) {
  return {
    date: stepFormValues.new_preferred_date ?? ctx.new_preferred_date ?? null,
    time: stepFormValues.new_preferred_time ?? ctx.new_preferred_time ?? null,
  }
}

export function activeFlowStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === EXTRA_SUPERVISION_TERMINAL_REJECT) return -1
  const idx = EXTRA_SUPERVISION_FLOW_STEPS.findIndex((s) => s.state === currentState)
  if (idx >= 0) return idx
  return 0
}

export function ScheduleChip({
  label, date, time, tone = '#0d9488', bg = '#f0fdfa', testId,
}) {
  const hasAny = date || time
  if (!hasAny) return null
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
    </div>
  )
}

export function ExtraSupervisionFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeFlowStepIndex(currentState)
  const rejected = currentState === EXTRA_SUPERVISION_TERMINAL_REJECT
  const completed = currentState === 'extra_session_completed'

  if (rejected) {
    return (
      <div
        data-testid="extra-supervision-flow-rejected"
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
        درخواست پایان یافت — سوپروایزر در حال حاضر امکان برگزاری جلسهٔ اضافی را اعلام نکرده است.
      </div>
    )
  }

  return (
    <div
      data-testid="extra-supervision-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact
          ? '1fr'
          : 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {EXTRA_SUPERVISION_FLOW_STEPS.map((step, i) => {
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
            {completed && i === EXTRA_SUPERVISION_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
