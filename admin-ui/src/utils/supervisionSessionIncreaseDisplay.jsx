/** نمایش مشترک زنجیره «افزایش جلسات هفتگی سوپرویژن» — فرایند ۲۱. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const SUPERVISION_INCREASE_FLOW_STEPS = [
  { key: 'request_submitted', state: 'request_submitted', label: 'ثبت زمان درخواستی' },
  { key: 'supervisor_review', state: 'supervisor_review', label: 'بررسی سوپروایزر' },
  { key: 'student_response', state: 'student_response', label: 'پاسخ به پیشنهاد جایگزین' },
  { key: 'session_added', state: 'session_added', label: 'جلسه اضافه شد' },
]

export const SUPERVISION_INCREASE_TERMINAL_REJECT = 'request_rejected'

export function parseWeeklyCount(raw) {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
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
  if (!s) return '—'
  return s
}

/** زمان درخواستی دانشجو — از context یا پیش‌نمایش فرم */
export function resolveStudentRequestedSchedule(ctx = {}, stepFormValues = {}) {
  const date = (
    stepFormValues.first_session_date
    ?? ctx.first_session_date
    ?? ctx.first_session_date_effective
  )
  const time = (
    stepFormValues.preferred_time_hhmm
    ?? ctx.preferred_time_hhmm
  )
  const weekday = (
    stepFormValues.preferred_weekday_fa
    ?? ctx.preferred_weekday_fa
  )
  return { date, time, weekday }
}

/** پیشنهاد جایگزین سوپروایزر */
export function resolveSupervisorAlternativeSchedule(ctx = {}) {
  return {
    date: ctx.supervisor_alternative_date ?? null,
    time: ctx.supervisor_alternative_time_hhmm ?? null,
  }
}

/** زمان جدید دانشجو در مرحلهٔ پاسخ (پیش‌نمایش فرم) */
export function resolveStudentCounterSchedule(ctx = {}, stepFormValues = {}) {
  return {
    date: stepFormValues.new_first_session_date ?? ctx.new_first_session_date ?? null,
    time: stepFormValues.new_preferred_time_hhmm ?? ctx.new_preferred_time_hhmm ?? null,
    note: stepFormValues.student_response_note ?? ctx.student_response_note ?? null,
  }
}

export function activeFlowStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === SUPERVISION_INCREASE_TERMINAL_REJECT) return -1
  const idx = SUPERVISION_INCREASE_FLOW_STEPS.findIndex((s) => s.state === currentState)
  if (idx >= 0) return idx
  if (currentState === 'session_added') return SUPERVISION_INCREASE_FLOW_STEPS.length - 1
  return 0
}

export function ScheduleChip({ label, date, time, weekday, tone = '#7c3aed', bg = '#f5f3ff', testId }) {
  const hasAny = date || time || weekday
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
      {weekday && (
        <div>
          <strong>روز هفته:</strong>
          {' '}
          {weekday}
        </div>
      )}
    </div>
  )
}

export function SupervisionIncreaseFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeFlowStepIndex(currentState)
  const rejected = currentState === SUPERVISION_INCREASE_TERMINAL_REJECT
  const completed = currentState === 'session_added'

  if (rejected) {
    return (
      <div
        data-testid="supervision-increase-flow-rejected"
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
        درخواست پایان یافت — سوپروایزر در حال حاضر امکان افزایش جلسات را اعلام نکرده است.
      </div>
    )
  }

  return (
    <div
      data-testid="supervision-increase-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact
          ? '1fr'
          : 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {SUPERVISION_INCREASE_FLOW_STEPS.map((step, i) => {
        const done = completed ? true : i < activeIdx
        const current = !completed && i === activeIdx
        const tone = done ? '#16a34a' : current ? '#7c3aed' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#f5f3ff' : '#f8fafc'
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
              color: done ? '#14532d' : current ? '#5b21b6' : '#64748b',
            }}
          >
            <div style={{ fontWeight: 800, marginBottom: '0.15rem' }}>
              {i + 1}
              .
              {' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
            {completed && i === SUPERVISION_INCREASE_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
