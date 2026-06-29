/** نمایش مشترک زنجیره «مشورت و تعیین آمادگی برای آغاز انترنی» — فرایند ۳۷. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

/** مراحل اصلی (milestone) فرایند ۳۷. */
export const INTERNSHIP_READINESS_FLOW_STEPS = [
  {
    key: 'request',
    label: 'درخواست ارتقا به انترن',
    states: ['auto_trigger', 'student_request'],
  },
  {
    key: 'supervision',
    label: 'بررسی کمیته نظارت',
    states: ['supervision_committee_review'],
  },
  {
    key: 'interview',
    label: 'مصاحبه کمیته پیشرفت',
    states: [
      'interview_scheduling',
      'interview_held',
      'interview_result_unconditional',
      'interview_result_conditional',
    ],
  },
  {
    key: 'contracts',
    label: 'قراردادها و سفته',
    states: ['contract_practice', 'contract_rules', 'promissory_note'],
  },
  {
    key: 'capacity',
    label: 'ظرفیت و ارجاع بیمار',
    states: ['capacity_check', 'pending_patient'],
  },
  {
    key: 'supervisor',
    label: 'انتخاب سوپروایزر',
    states: ['supervisor_selection', 'first_session_payment'],
  },
  {
    key: 'started',
    label: 'آغاز انترنی',
    states: ['internship_started'],
  },
]

export const INTERNSHIP_TERMINAL_STOP = new Set([
  'supervision_rejected',
  'interview_result_retry',
])

export const INTERNSHIP_STOP_MESSAGES = {
  supervision_rejected:
    'کمیته نظارت مجوز ورود به انترنی را صادر نکرد. برای پیگیری از طریق تیکت با بخش آموزش تماس بگیرید.',
  interview_result_retry:
    'بر اساس نتیجه مصاحبه، فعلاً آمادگی لازم تأیید نشد. پس از گذراندن ۳۰ ساعت درمان آموزشی بیشتر، درخواست مصاحبه مجدد به‌صورت خودکار فعال می‌شود.',
}

/** برچسب فارسی هر وضعیت فرایند ۳۷. */
export const INTERNSHIP_STATE_LABELS = {
  auto_trigger: 'شروع خودکار پس از پاس تئوری تکنیک ۳',
  student_request: 'ثبت درخواست ارتقا به انترن',
  supervision_committee_review: 'بررسی و صدور مجوز کمیته نظارت',
  supervision_rejected: 'رد توسط کمیته نظارت',
  interview_scheduling: 'تنظیم وقت مصاحبه',
  interview_held: 'برگزاری مصاحبه',
  interview_result_unconditional: 'قبولی بدون شرط — ۳ ساعت',
  interview_result_conditional: 'قبولی مشروط — ۱ ساعت',
  interview_result_retry: 'درخواست دوباره پس از ۳۰ ساعت درمان',
  contract_practice: 'امضای قرارداد پرکیس',
  contract_rules: 'امضای قوانین اداری/آموزشی/بالینی',
  promissory_note: 'تحویل سفته حضوری',
  capacity_check: 'بررسی بیمار موجود برای ارجاع',
  pending_patient: 'منتظر بیمار',
  supervisor_selection: 'انتخاب سوپروایزر و زمان',
  first_session_payment: 'پرداخت جلسه اول سوپرویژن',
  internship_started: 'انترنی آغاز شد',
}

export const INTERVIEW_RESULT_LABELS = {
  unconditional: 'قبولی بدون شرط (۳ ساعت در هفته)',
  conditional: 'قبولی مشروط (۱ ساعت در هفته)',
  retry: 'درخواست دوباره پس از ۳۰ ساعت درمان',
}

export const MEETING_TYPE_LABELS = {
  in_person: 'حضوری — انستیتو روانکاوی تهران',
  online: 'آنلاین',
}

const SYSTEM_WAIT_STATES = new Set([
  'auto_trigger',
  'interview_result_unconditional',
  'interview_result_conditional',
  'capacity_check',
  'pending_patient',
])

export function labelInternshipState(state) {
  if (!state) return '—'
  return INTERNSHIP_STATE_LABELS[state] || state
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

export function fmtRialAsToman(rial, fallbackToman) {
  const toman = fallbackToman != null
    ? Number(fallbackToman)
    : rial != null
      ? Math.round(Number(rial) / 10)
      : null
  if (!Number.isFinite(toman)) return null
  return `${toman.toLocaleString('fa-IR')} تومان`
}

export function isInternshipStopState(state) {
  return INTERNSHIP_TERMINAL_STOP.has(state)
}

export function isSystemWaitState(state) {
  return SYSTEM_WAIT_STATES.has(state)
}

export function activeInternshipStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'internship_started') return INTERNSHIP_READINESS_FLOW_STEPS.length - 1
  if (isInternshipStopState(currentState)) return -1
  const idx = INTERNSHIP_READINESS_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function resolveInterviewSchedule(ctx = {}) {
  return {
    date: ctx.interview_date ?? ctx.interviewDate ?? null,
    time: ctx.interview_time ?? ctx.interviewTime ?? null,
    meetingType: ctx.meeting_type ?? ctx.meetingType ?? null,
    link: ctx.interview_link ?? ctx.meeting_link ?? ctx.online_link ?? null,
    location: ctx.interview_location ?? ctx.meeting_location ?? 'انستیتو روانکاوی تهران',
    windowStart: ctx.interview_window_start ?? ctx.internship_interview_window_start ?? null,
    windowEnd: ctx.interview_window_end ?? ctx.internship_interview_window_end ?? null,
  }
}

export function resolveInterviewResult(ctx = {}) {
  const raw = ctx.interview_result ?? ctx.result ?? ctx.interview_outcome ?? null
  const weeklyHours = ctx.weekly_hours_limit
    ?? ctx.weekly_hours
    ?? ctx.intern_weekly_hours
    ?? (raw === 'unconditional' ? 3 : raw === 'conditional' ? 1 : null)

  return {
    result: raw,
    resultLabel: INTERVIEW_RESULT_LABELS[raw] || null,
    weeklyHours: weeklyHours != null && weeklyHours !== '' ? Number(weeklyHours) : null,
  }
}

export function resolveSupervisorSelection(ctx = {}) {
  return {
    supervisorName: ctx.supervisor_name ?? ctx.selected_supervisor_name ?? ctx.supervisor_display_name ?? null,
    supervisorId: ctx.supervisor_id ?? ctx.selected_supervisor_id ?? null,
    sessionDay: ctx.session_day ?? ctx.supervision_day ?? ctx.selected_day ?? null,
    sessionTime: ctx.session_time ?? ctx.supervision_time ?? ctx.selected_time ?? null,
    firstSessionDate: ctx.first_session_date ?? ctx.supervision_start_date ?? null,
  }
}

export function resolveInternshipContext(ctx = {}) {
  const interview = resolveInterviewSchedule(ctx)
  const result = resolveInterviewResult(ctx)
  const supervisor = resolveSupervisorSelection(ctx)

  return {
    interview,
    result,
    supervisor,
    patientAvailable: ctx.patient_available ?? ctx.has_patient_for_referral ?? null,
    promissoryReceived: ctx.promissory_received ?? ctx.promissory_note_received ?? false,
    paymentAmountRial: ctx.payment_amount_rial != null
      ? Number(ctx.payment_amount_rial)
      : Math.round(Number(ctx.invoice_amount || ctx.session_fee_toman || 0) * 10),
  }
}

export function InternshipReadinessFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeInternshipStepIndex(currentState)
  const stopped = isInternshipStopState(currentState)
  const completed = currentState === 'internship_started'

  if (stopped) {
    return (
      <div
        data-testid="internship-readiness-flow-stopped"
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
        {INTERNSHIP_STOP_MESSAGES[currentState]}
      </div>
    )
  }

  return (
    <div
      data-testid="internship-readiness-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {INTERNSHIP_READINESS_FLOW_STEPS.map((step, i) => {
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
            {completed && i === INTERNSHIP_READINESS_FLOW_STEPS.length - 1 && (
              <div style={{ fontSize: '0.72rem' }}>✓ تکمیل</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function ScheduleChip({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (!value) return null
  return (
    <div
      style={{
        padding: '0.55rem 0.7rem',
        borderRadius: '8px',
        background: bg,
        borderRight: `3px solid ${tone}`,
        fontSize: '0.82rem',
        lineHeight: 1.55,
      }}
    >
      <div style={{ fontSize: '0.72rem', color: '#64748b', marginBottom: '0.1rem' }}>{label}</div>
      <div style={{ fontWeight: 700, color: '#1e293b' }}>{value}</div>
    </div>
  )
}
