/** نمایش مشترک فرایند ۶۰ — بازگشت به کل آموزش پس از مرخصی. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const RETURN_FLOW_STEPS = [
  {
    key: 'start',
    label: 'شروع بازگشت',
    states: ['return_request'],
  },
  {
    key: 'therapy',
    label: 'درمانگر آموزشی',
    states: ['therapist_selection', 'therapy_24h_scheduled', 'therapy_payment_pending', 'therapy_completed'],
  },
  {
    key: 'supervision',
    label: 'سوپرویژن (انترن)',
    states: ['supervisor_selection', 'supervision_24h_scheduled', 'supervision_payment_pending'],
  },
  {
    key: 'unlock',
    label: 'بازگشایی ثبت‌نام',
    states: ['registration_unlocked', 'return_complete'],
  },
]

export const RETURN_STATE_HINTS = {
  return_request:
    'برای بازگشت به کل آموزش، ابتدا درمانگر آموزشی و ساعات هفتگی را انتخاب و جلسهٔ اول را پرداخت کنید. دکمهٔ ادامه را بزنید.',
  therapist_selection:
    'درمانگر آموزشی و تعداد جلسات هفتگی را در فرم زیر مشخص کنید. دوره جامع: دقیقاً ۲ ساعت؛ دوره آشنایی: ۱ تا ۲ ساعت.',
  therapy_24h_scheduled:
    'تاریخ شروع درمان بر اساس قانون ۲۴ ساعت محاسبه می‌شود. این مرحله معمولاً خودکار است.',
  therapy_payment_pending:
    'از بخش پرداخت سپ همین صفحه استفاده کنید. پس از بازگشت از بانک، صفحه را یک‌بار تازه کنید.',
  therapy_completed:
    'درمان آموزشی ثبت شد. در صورت انترن بودن، مرحلهٔ انتخاب سوپروایزر باز می‌شود.',
  supervisor_selection:
    'از فهرست سوپروایزرها یک نفر و زمان جلسه (۱ ساعت در هفته) انتخاب کنید.',
  supervision_24h_scheduled:
    'تاریخ شروع سوپرویژن بر اساس قانون ۲۴ ساعت محاسبه می‌شود.',
  supervision_payment_pending:
    'هزینهٔ جلسهٔ اول سوپرویژن را از درگاه بانک همین صفحه بپردازید.',
  registration_unlocked:
    'محدودیت ثبت‌نام دروس برداشته شد. می‌توانید در ترم جدید ثبت‌نام کنید.',
  return_complete:
    'بازگشت به کل آموزش با موفقیت تکمیل شد.',
}

export const COURSE_TYPE_LABELS = {
  comprehensive: 'دوره جامع',
  introductory: 'دوره آشنایی',
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso, { dateStyle: 'medium' })
  } catch {
    return String(iso).slice(0, 10)
  }
}

export function fmtTimeHm(val) {
  if (!val) return '—'
  const s = String(val)
  if (/^\d{1,2}:\d{2}/.test(s)) return s.slice(0, 5)
  return s
}

export function fmtRialAsToman(rial) {
  const n = Number(rial)
  if (!Number.isFinite(n) || n <= 0) return '—'
  return `${Math.round(n / 10).toLocaleString('fa-IR')} تومان`
}

export function resolveReturnContext(ctx = {}) {
  const courseType = ctx.course_type || 'introductory'
  const isIntern = ctx.is_intern === true
  return {
    courseType,
    courseTypeLabel: ctx.course_type_display_fa || COURSE_TYPE_LABELS[courseType] || courseType,
    isIntern,
    isInternLabel: ctx.is_intern_display_fa || (isIntern ? 'انترن' : 'غیر انترن'),
    weeklyHoursHint: ctx.weekly_hours_hint_fa || (courseType === 'comprehensive' ? '۲ ساعت در هفته' : '۱ تا ۲ ساعت در هفته'),
    supervisionHoursHint: ctx.supervision_hours_hint_fa || (isIntern ? '۱ ساعت در هفته' : '—'),
    therapistName: ctx.therapist_name || ctx.selected_therapist_name || null,
    therapistId: ctx.therapist_id || null,
    therapyFirstSessionAt: ctx.therapy_first_session_at || ctx.first_session_date_effective || null,
    therapyPaymentRial: Number(ctx.therapy_payment_amount_rial) || 0,
    supervisorName: ctx.supervisor_name || ctx.selected_supervisor_name || null,
    supervisorId: ctx.supervisor_id || null,
    supervisionDay: ctx.supervision_day || null,
    supervisionTime: ctx.supervision_time || null,
    supervisionFirstSessionAt: ctx.supervision_first_session_at || null,
    supervisionPaymentRial: Number(ctx.supervision_payment_amount_rial) || 0,
    registrationUnlockedAt: ctx.registration_unlocked_at || null,
  }
}

export function isReturnCompleteState(state) {
  return state === 'return_complete'
}

export function isSystemWaitState(state) {
  return ['therapy_24h_scheduled', 'supervision_24h_scheduled', 'therapy_completed', 'registration_unlocked'].includes(state)
}

export function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (value == null || value === '' || value === '—') return null
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

export function ScheduleChip({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (!value) return null
  return (
    <div style={{ padding: '0.55rem 0.7rem', borderRadius: '8px', background: bg, borderRight: `3px solid ${tone}` }}>
      <div style={{ fontSize: '0.72rem', color: '#64748b' }}>{label}</div>
      <div style={{ fontSize: '0.92rem', fontWeight: 700, color: tone }}>{value}</div>
    </div>
  )
}

export function HintBlock({ children, tone = '#2563eb', bg = '#eff6ff' }) {
  return (
    <div
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        fontSize: '0.84rem',
        lineHeight: 1.7,
        color: tone,
      }}
    >
      {children}
    </div>
  )
}

export function ReturnFlowStepper({ currentState, compact = false }) {
  const activeIdx = RETURN_FLOW_STEPS.findIndex((step) => step.states.includes(currentState))
  return (
    <div
      data-testid="return-flow-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {RETURN_FLOW_STEPS.map((step, idx) => {
        const done = activeIdx > idx
        const active = activeIdx === idx
        const skipSupervision = step.key === 'supervision' && currentState === 'return_complete'
          && !['supervisor_selection', 'supervision_24h_scheduled', 'supervision_payment_pending'].some(
            (s) => RETURN_FLOW_STEPS.find((st) => st.key === 'supervision')?.states.includes(s),
          )
        if (skipSupervision && !active && !done) return null
        return (
          <div
            key={step.key}
            style={{
              flex: compact ? '1 1 45%' : '1 1 120px',
              padding: compact ? '0.45rem 0.55rem' : '0.55rem 0.7rem',
              borderRadius: '8px',
              fontSize: compact ? '0.72rem' : '0.78rem',
              fontWeight: active ? 800 : 600,
              textAlign: 'center',
              background: done ? '#f0fdf4' : active ? '#eff6ff' : '#f8fafc',
              color: done ? '#16a34a' : active ? '#2563eb' : '#64748b',
              border: `1px solid ${done ? '#bbf7d0' : active ? '#bfdbfe' : '#e2e8f0'}`,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}
