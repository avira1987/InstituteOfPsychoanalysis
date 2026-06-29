/** نمایش مشترک فرایند ۷۱ — ارتقا به درمانگر آموزشی. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const ET_UPGRADE_FLOW_STEPS = [
  { key: 'request', label: 'درخواست و احراز شرایط', states: ['student_start', 'eligibility_failed'] },
  { key: 'monitoring', label: 'کمیته نظارت', states: ['monitoring_review', 'monitoring_rejected'] },
  {
    key: 'interview',
    label: 'مصاحبه کمیته درمان آموزشی',
    states: ['interview_scheduling', 'interview_held', 'interview_rejected'],
  },
  {
    key: 'therapy',
    label: 'درمان شخصی ۵۰ ساعت',
    states: [
      'therapy_readiness_check',
      'therapy_frequency_adjustment',
      'therapy_frequency_escalation',
      'personal_therapy_hours',
      'therapist_selection',
      'therapist_committee_review',
    ],
  },
  {
    key: 'supervision',
    label: 'سوپرویژن ۵۰ ساعت',
    states: [
      'supervision_readiness_check',
      'supervision_frequency_adjustment',
      'supervision_restart',
      'supervision_hours',
      'supervisor_selection',
    ],
  },
  { key: 'slots', label: 'ثبت وقت ET', states: ['et_availability_slots', 'promotion_completed'] },
]

export const ET_STOP_STATES = new Set([
  'eligibility_failed',
  'monitoring_rejected',
  'interview_rejected',
])

export const ET_STOP_MESSAGES = {
  eligibility_failed:
    'دانشجوی گرامی، شما شرایط لازم جهت ارتقا به درمانگر آموزشی را کسب نکرده‌اید.',
  monitoring_rejected:
    'صلاحیت شما توسط کمیته نظارت تأیید نشد. برای پیگیری با بخش آموزش تماس بگیرید.',
  interview_rejected:
    'صلاحیت شما پس از مصاحبه تأیید نشد. برای پیگیری با کمیته درمان آموزشی و سوپرویژن تماس بگیرید.',
}

export const ET_STATE_HINTS = {
  student_start: 'شرایط ارتقا را مطالعه کنید و درخواست را ثبت کنید.',
  monitoring_review: 'پرونده در کمیته نظارت در حال بررسی است.',
  interview_scheduling: 'کمیته درمان آموزشی در حال تنظیم وقت مصاحبه است.',
  interview_held: 'مصاحبه برگزار می‌شود یا در حال برگزاری است.',
  therapy_frequency_adjustment:
    'درمان شخصی را به حداقل یک جلسه در هفته افزایش دهید. مهلت: ۱۰ روز.',
  personal_therapy_hours:
    '۵۰ ساعت دیگر درمان شخصی دریافت کنید. قوانین سختگیرانه غیبت/کنسلی اعمال نمی‌شود.',
  therapist_selection: 'از شیت وقت‌های آزاد درمانگران، درمانگر پیشنهادی را انتخاب کنید.',
  therapist_committee_review: 'درمانگر پیشنهادی در حال بررسی توسط کمیته است.',
  supervision_frequency_adjustment:
    'سوپرویژن فردی را به دو جلسه در ماه افزایش دهید.',
  supervision_restart:
    'سوپرویژن قبلی قطع شده؛ با عضو هیئت علمی کامل سوپرویژن را آغاز کنید.',
  supervision_hours: 'تا تکمیل ۵۰ ساعت سوپرویژن فردی ادامه دهید.',
  supervisor_selection:
    'از شیت وقت‌های آزاد سوپروایزرها (هیئت علمی کامل) زمان انتخاب کنید.',
  et_availability_slots:
    'دو زمان خالی برای ارائه خدمات به‌عنوان درمانگر آموزشی ثبت کنید.',
  promotion_completed: 'ارتقا به درمانگر آموزشی با موفقیت تکمیل شد.',
}

export const MEETING_TYPE_LABELS = {
  in_person: 'حضوری',
  online: 'آنلاین',
}

const SYSTEM_WAIT_STATES = new Set([
  'therapy_readiness_check',
  'supervision_readiness_check',
])

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

export function isUpgradeStopState(state) {
  return ET_STOP_STATES.has(state)
}

export function isSystemWaitState(state) {
  return SYSTEM_WAIT_STATES.has(state)
}

export function resolveUpgradeContext(ctx = {}) {
  const therapyRemaining = Number(ctx.et_therapy_hours_remaining ?? 50)
  const therapyCompleted = Number(ctx.et_therapy_hours_completed ?? 0)
  const therapyTarget = Number(ctx.et_therapy_hours_target ?? 50)
  const supervisionRemaining = Number(ctx.et_supervision_hours_remaining ?? 50)
  const supervisionCompleted = Number(ctx.et_supervision_hours_completed ?? 0)
  const supervisionTarget = Number(ctx.et_supervision_hours_target ?? 50)

  return {
    eligibilityMet: ctx.et_eligibility_met === true,
    eligibilitySummary: ctx.et_eligibility_summary_fa || '—',
    therapyWeeklySessions: ctx.et_therapy_weekly_sessions,
    therapyActive: ctx.et_therapy_active === true,
    therapyRemaining,
    therapyCompleted,
    therapyTarget,
    therapyProgressPct: therapyTarget > 0
      ? Math.min(100, Math.round((therapyCompleted / therapyTarget) * 100))
      : 0,
    supervisionMonthlySessions: ctx.et_supervision_monthly_sessions,
    supervisionActive: ctx.et_supervision_active === true,
    supervisionRemaining,
    supervisionCompleted,
    supervisionTarget,
    supervisionProgressPct: supervisionTarget > 0
      ? Math.min(100, Math.round((supervisionCompleted / supervisionTarget) * 100))
      : 0,
    interviewDate: ctx.interview_date,
    interviewTime: ctx.interview_time,
    meetingType: ctx.meeting_type,
    selectedTherapistLabel: ctx.selected_therapist_label || ctx.therapist_id || '—',
    selectedSupervisorLabel: ctx.selected_supervisor_label || ctx.supervisor_id || '—',
    slot1: ctx.et_slot_1,
    slot2: ctx.et_slot_2,
  }
}

export function EducationalTherapistFlowStepper({ currentState }) {
  const activeIdx = ET_UPGRADE_FLOW_STEPS.findIndex((step) =>
    step.states.includes(currentState),
  )
  const idx = activeIdx >= 0 ? activeIdx : 0

  return (
    <div
      data-testid="et-upgrade-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
        gap: '0.5rem',
        marginBottom: '1rem',
      }}
    >
      {ET_UPGRADE_FLOW_STEPS.map((step, i) => {
        const done = i < idx || currentState === 'promotion_completed'
        const active = i === idx
        return (
          <div
            key={step.key}
            style={{
              padding: '0.5rem 0.6rem',
              borderRadius: '8px',
              fontSize: '0.75rem',
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

export function ProgressBar({ label, completed, target, pct }) {
  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '0.25rem' }}>
        <span>{label}</span>
        <span>
          {completed}
          /
          {target}
          {' '}
          ساعت
        </span>
      </div>
      <div style={{ height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: '#2563eb',
            borderRadius: '4px',
            transition: 'width 0.3s',
          }}
        />
      </div>
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
