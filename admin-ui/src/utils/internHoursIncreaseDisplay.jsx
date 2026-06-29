/** نمایش مشترک «افزایش حداکثر ساعت‌های ارائه درمان انترن» — فرایند ۳۹. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const INTERN_HOURS_FLOW_STEPS = [
  { key: 'deadline_reached', state: 'deadline_reached', label: 'رسیدن سررسید' },
  { key: 'supervision_review', state: 'supervision_review', label: 'بررسی کمیته' },
  { key: 'approved_time_coordination', state: 'approved_time_coordination', label: 'هماهنگی زمان‌ها' },
  { key: 'hours_increased', state: 'hours_increased', label: 'افزایش ظرفیت' },
]

export const INTERN_HOURS_TERMINAL_REJECT = 'rejected_referral'

/** الگوی بدون شرط: ماه → ساعت اضافه */
export const STANDARD_HOURS_BY_MONTH = {
  4: 2,
  7: 2,
  12: 3,
  16: 3,
  20: 3,
  24: 4,
  28: 5,
}

/** الگوی مشروط (انترن مشروط): ماه → ساعت اضافه */
export const CONDITIONAL_HOURS_BY_MONTH = {
  4: 1,
  7: 1,
  12: 1,
}

const DAY_LABELS = {
  saturday: 'شنبه',
  sunday: 'یکشنبه',
  monday: 'دوشنبه',
  tuesday: 'سه‌شنبه',
  wednesday: 'چهارشنبه',
  thursday: 'پنج‌شنبه',
  friday: 'جمعه',
  sat: 'شنبه',
  sun: 'یکشنبه',
  mon: 'دوشنبه',
  tue: 'سه‌شنبه',
  wed: 'چهارشنبه',
  thu: 'پنج‌شنبه',
  fri: 'جمعه',
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

export function labelDay(raw) {
  if (!raw) return '—'
  const key = String(raw).trim().toLowerCase()
  return DAY_LABELS[key] || String(raw)
}

export function labelDisciplinaryStatus(value) {
  if (value === 'no_violation') return 'فاقد تخلف'
  if (value === 'has_violation') return 'دارای تخلف — ارجاع به کمیته تخلفات'
  if (!value) return null
  return String(value)
}

/** اطلاعات سررسید milestone از context */
export function resolveMilestoneInfo(ctx = {}) {
  const month = ctx.intern_month ?? ctx.milestone_month ?? null
  const monthNum = month != null ? Number(month) : null
  const isConditional = ctx.conditional_intern === true
    || ctx.is_conditional_intern === true
    || ctx.intern_pattern === 'conditional'

  const hoursMap = isConditional ? CONDITIONAL_HOURS_BY_MONTH : STANDARD_HOURS_BY_MONTH
  const hoursIncrease = Number.isFinite(monthNum) ? hoursMap[monthNum] ?? null : null

  return {
    month: monthNum,
    isConditional,
    hoursIncrease,
    patternLabel: isConditional ? 'الگوی مشروط (۴+۱، ۷+۱، ۱۲+۱)' : 'الگوی استاندارد (۴+۲ تا ۲۸+۵)',
  }
}

/** زمان‌های توافق‌شده از context یا پیش‌نمایش فرم */
export function resolveAgreedTimes(ctx = {}, stepFormValues = {}) {
  const fromForm = stepFormValues.agreed_times
  const fromCtx = ctx.agreed_times
  const raw = fromForm ?? fromCtx
  if (!Array.isArray(raw)) return []
  return raw.filter((row) => row && (row.day || row.start_time || row.end_time))
}

export function activeFlowStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === INTERN_HOURS_TERMINAL_REJECT) return -1
  const idx = INTERN_HOURS_FLOW_STEPS.findIndex((s) => s.state === currentState)
  if (idx >= 0) return idx
  return 0
}

export function AgreedTimeRow({ row, index }) {
  if (!row) return null
  return (
    <div
      data-testid={`intern-hours-agreed-time-${index}`}
      style={{
        padding: '0.55rem 0.75rem',
        borderRadius: '8px',
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
        fontSize: '0.84rem',
        lineHeight: 1.65,
      }}
    >
      <strong>
        {index + 1}
        .
      </strong>
      {' '}
      <strong>روز:</strong>
      {' '}
      {labelDay(row.day)}
      {' '}
      —
      {' '}
      <strong>از</strong>
      {' '}
      <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtTimeHm(row.start_time)}</span>
      {' '}
      <strong>تا</strong>
      {' '}
      <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtTimeHm(row.end_time)}</span>
    </div>
  )
}

export function InternHoursFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeFlowStepIndex(currentState)
  const rejected = currentState === INTERN_HOURS_TERMINAL_REJECT
  const completed = currentState === 'hours_increased'

  if (rejected) {
    return (
      <div
        data-testid="intern-hours-flow-rejected"
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
        افزایش ظرفیت تأیید نشد — پرونده به کمیته تخلفات ارجاع داده می‌شود و به دانشجو پیامک ارسال می‌شود.
      </div>
    )
  }

  return (
    <div
      data-testid="intern-hours-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact
          ? '1fr'
          : 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {INTERN_HOURS_FLOW_STEPS.map((step, i) => {
        const done = completed ? true : i < activeIdx
        const current = !completed && i === activeIdx
        const tone = done ? '#16a34a' : current ? '#d97706' : '#94a3b8'
        const bg = done ? '#f0fdf4' : current ? '#fffbeb' : '#f8fafc'
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
              color: done ? '#14532d' : current ? '#92400e' : '#64748b',
            }}
          >
            <div style={{ fontWeight: 800, marginBottom: '0.15rem' }}>
              {i + 1}
              .
              {' '}
              {step.label}
            </div>
            {current && <div style={{ fontSize: '0.72rem' }}>← مرحلهٔ فعلی</div>}
            {completed && i === INTERN_HOURS_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
