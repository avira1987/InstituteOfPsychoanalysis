/** نمایش مشترک فرایند ۴۷ — ارتقا به کمک‌مدرس. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const TA_UPGRADE_FLOW_STEPS = [
  { key: 'request', label: 'درخواست و احراز شرایط', states: ['student_click', 'conditions_not_met'] },
  { key: 'supervision', label: 'کمیته نظارت', states: ['supervision_review', 'supervision_rejected'] },
  {
    key: 'interview',
    label: 'مصاحبه کمیته دروس',
    states: ['interview_scheduling', 'interview_held', 'course_committee_rejected'],
  },
  { key: 'tracks', label: 'تعیین رسته', states: ['track_selection'] },
  { key: 'commitment', label: 'تعهدنامه و ثبت', states: ['commitment_signature', 'ta_registered'] },
]

export const TA_STOP_STATES = new Set([
  'conditions_not_met',
  'supervision_rejected',
  'course_committee_rejected',
])

export const TA_STOP_MESSAGES = {
  conditions_not_met:
    'دانشجوی گرامی، شما شرایط لازم جهت ارتقا به کمک‌مدرس را کسب نکرده‌اید. '
    + 'چهار شرط: پاس شدن دروس ترم دوم جامع، معدل B، ۵۰ ساعت درمان آموزشی، و شروع انترنی.',
  supervision_rejected:
    'صلاحیت شما توسط کمیته نظارت تأیید نشد. برای پیگیری با بخش آموزش تماس بگیرید.',
  course_committee_rejected:
    'پس از مصاحبه، صلاحیت شما توسط کمیته دروس تأیید نشد. برای پیگیری با کمیته دروس تماس بگیرید.',
}

export const TA_STATE_HINTS = {
  student_click:
    'چهار شرط ارتقا را در باکس زیر بررسی کنید. در صورت احراز همهٔ شروط، دکمهٔ «ادامه و ثبت مرحله» را بزنید.',
  supervision_review: 'پرونده در کمیته نظارت در حال بررسی است.',
  interview_scheduling: 'کمیته دروس در حال تنظیم وقت مصاحبه است.',
  interview_held: 'مصاحبه در زمان مقرر برگزار می‌شود یا برگزار شده است.',
  track_selection: 'کمیته دروس رسته‌های توافق‌شده را ثبت می‌کند.',
  commitment_signature:
    'متن تعهدنامه را مطالعه کنید، گزینهٔ پذیرش را تأیید و کد پیامکی را وارد کنید.',
  ta_registered: 'ارتقا به کمک‌مدرس با موفقیت تکمیل شد.',
}

export const MEETING_TYPE_LABELS = {
  in_person: 'حضوری',
  online: 'آنلاین',
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

export function isTaStopState(state) {
  return TA_STOP_STATES.has(state)
}

function defaultConditionsPreview(ctx) {
  return [
    {
      key: 'term2_courses',
      label_fa: 'پاس شدن دروس ترم دوم دوره جامع',
      met: ctx.ta_term2_courses_met === true,
    },
    {
      key: 'gpa_b',
      label_fa: `معدل حداقل B (فعلی: ${ctx.ta_cumulative_gpa ?? '—'})`,
      met: ctx.ta_gpa_met === true,
    },
    {
      key: 'therapy_50h',
      label_fa: `حداقل ۵۰ ساعت درمان آموزشی (فعلی: ${ctx.ta_therapy_hours_completed ?? 0})`,
      met: ctx.ta_therapy_met === true,
    },
    {
      key: 'internship_started',
      label_fa: 'شروع دوره انترنی',
      met: ctx.ta_intern_met === true,
    },
  ]
}

export function resolveTaUpgradeContext(ctx = {}) {
  const preview = Array.isArray(ctx.ta_conditions_preview) && ctx.ta_conditions_preview.length
    ? ctx.ta_conditions_preview
    : defaultConditionsPreview(ctx)

  const tracksRaw = ctx.tracks
  const tracks = Array.isArray(tracksRaw)
    ? tracksRaw
    : tracksRaw != null && tracksRaw !== ''
      ? [tracksRaw]
      : []

  return {
    eligibilityMet: ctx.ta_eligibility_met === true,
    eligibilitySummary: ctx.ta_eligibility_summary_fa || '—',
    conditionsPreview: preview,
    therapyCompleted: Number(ctx.ta_therapy_hours_completed ?? 0),
    therapyTarget: Number(ctx.ta_therapy_hours_target ?? 50),
    interviewDate: ctx.interview_date,
    interviewTime: ctx.interview_time,
    meetingType: ctx.meeting_type,
    tracks,
    trackLabelsFa: ctx.ta_track_labels_fa || tracks,
  }
}

export function TaUpgradeFlowStepper({ currentState, compact = false }) {
  const activeIdx = TA_UPGRADE_FLOW_STEPS.findIndex((step) =>
    step.states.includes(currentState),
  )
  const idx = activeIdx >= 0 ? activeIdx : 0

  return (
    <div
      data-testid="ta-upgrade-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact
          ? 'repeat(auto-fit, minmax(72px, 1fr))'
          : 'repeat(auto-fit, minmax(100px, 1fr))',
        gap: '0.5rem',
        marginBottom: compact ? '0.65rem' : '1rem',
      }}
    >
      {TA_UPGRADE_FLOW_STEPS.map((step, i) => {
        const done = i < idx || currentState === 'ta_registered'
        const active = i === idx
        return (
          <div
            key={step.key}
            style={{
              padding: compact ? '0.4rem 0.45rem' : '0.5rem 0.6rem',
              borderRadius: '8px',
              fontSize: compact ? '0.7rem' : '0.75rem',
              fontWeight: active ? 700 : 500,
              textAlign: 'center',
              background: done ? '#f0fdf4' : active ? '#eff6ff' : '#f8fafc',
              borderRight: `3px solid ${done ? '#16a34a' : active ? '#2563eb' : '#e2e8f0'}`,
              color: done ? '#166534' : active ? '#1d4ed8' : '#64748b',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function HintBlock({ children, tone = '#2563eb', bg = '#eff6ff' }) {
  if (!children) return null
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
        color: '#334155',
      }}
    >
      {children}
    </div>
  )
}

export function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
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

export function EligibilityChecklistTiles({ items = [] }) {
  if (!items.length) return null
  return (
    <div
      data-testid="ta-eligibility-checklist"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '0.55rem',
        marginBottom: '0.85rem',
      }}
    >
      {items.map((row) => {
        const met = row.met === true
        return (
          <div
            key={row.key || row.label_fa}
            style={{
              padding: '0.65rem 0.75rem',
              borderRadius: '8px',
              background: met ? '#f0fdf4' : '#fffbeb',
              borderRight: `3px solid ${met ? '#16a34a' : '#d97706'}`,
              fontSize: '0.8rem',
              lineHeight: 1.55,
            }}
          >
            <span style={{ marginLeft: '0.35rem' }}>{met ? '✓' : '✗'}</span>
            {row.label_fa}
          </div>
        )
      })}
    </div>
  )
}

export function TrackChips({ tracks = [], labels = null }) {
  const list = Array.isArray(labels) && labels.length ? labels : tracks
  if (!list.length) return null
  return (
    <div
      data-testid="ta-selected-tracks"
      style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.75rem' }}
    >
      {list.map((t) => (
        <span
          key={String(t)}
          style={{
            padding: '0.35rem 0.65rem',
            borderRadius: '999px',
            background: '#f5f3ff',
            color: '#5b21b6',
            fontSize: '0.78rem',
            fontWeight: 600,
          }}
        >
          {String(t)}
        </span>
      ))}
    </div>
  )
}
