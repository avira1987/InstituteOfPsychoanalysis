/** نمایش مشترک فرایند ۶۷ — خاتمه درس سوپرویژن زنده. */

import React from 'react'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { resolveEvaluationSummary, EvaluationSummaryBlock, HintBlock, InfoTile } from './articleWritingCompletionDisplay'

export { HintBlock, InfoTile, EvaluationSummaryBlock, resolveEvaluationSummary }

export const LIVE_SUPERVISION_FLOW_STEPS = [
  { key: 'active', label: 'کلاس فعال (۱۵+۳)', states: ['sessions_in_progress'] },
  { key: 'mirror_write', label: 'پیاده‌سازی پشت‌آینه', states: ['mirror_implementation_pending'] },
  { key: 'mirror_eval', label: 'ارزیابی پشت‌آینه', states: ['mirror_eval_pending'] },
  { key: 'final_eval', label: 'ارزیابی نهایی', states: ['final_eval_pending'] },
  { key: 'done', label: 'خاتمه درس', states: ['completed'] },
]

export const LIVE_SUPERVISION_STATE_LABELS = {
  sessions_in_progress: 'کلاس سوپرویژن زنده فعال',
  mirror_implementation_pending: 'منتظر پیاده‌سازی پشت‌آینه (۵ روز)',
  mirror_eval_pending: 'منتظر ارزیابی ۳ جلسه پشت‌آینه (۵ روز)',
  final_eval_pending: 'منتظر ارزیابی نهایی (تا ۲۴:۰۰)',
  completed: 'درس تکمیل شد',
  mirror_write_violation: 'تأخیر پیاده‌سازی — گزارش تخلف',
  mirror_eval_violation: 'تأخیر ارزیابی پشت‌آینه — گزارش تخلف',
  final_eval_delay: 'تأخیر ارزیابی نهایی — کمیته دروس',
}

const VIOLATION_STATES = new Set([
  'mirror_write_violation',
  'mirror_eval_violation',
  'final_eval_delay',
])

const SLA_CONFIG = {
  mirror_implementation_pending: {
    days: 5,
    keys: ['mirror_session_date', 'last_mirror_at', 'started_at'],
    title: 'مهلت پیاده‌سازی جلسه پشت‌آینه (۵ روز)',
  },
  mirror_eval_pending: {
    days: 5,
    keys: ['third_mirror_at', 'last_mirror_at', 'started_at'],
    title: 'مهلت ارزیابی پشت‌آینه مدرس (۵ روز)',
  },
  final_eval_pending: {
    days: 1,
    keys: ['eighteenth_at', 'started_at'],
    title: 'مهلت ارزیابی نهایی (تا ۲۴:۰۰ همان روز)',
  },
}

export const NORMAL_REQUIRED = 15
export const MIRROR_REQUIRED = 3
export const TOTAL_REQUIRED = 18

export function labelLiveSupervisionState(state) {
  if (!state) return '—'
  return LIVE_SUPERVISION_STATE_LABELS[state] || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function isLiveSupervisionViolationState(state) {
  return VIOLATION_STATES.has(state)
}

export function isLiveSupervisionProcess(code) {
  return code === 'live_supervision_course_completion'
}

export function courseCodeFromContext(ctx = {}) {
  return ctx.course_code || ctx.course_id || ctx.lesson_course_label || ctx.course_name || ''
}

export function resolveLiveSupervisionContext(ctx = {}, lmsProgress = null) {
  const prog = lmsProgress || {}
  return {
    courseCode: courseCodeFromContext(ctx),
    courseName: ctx.course_name || ctx.course_code || 'سوپرویژن زنده',
    studentName: ctx.student_name || null,
    normalCount: prog.normal_count ?? ctx.live_supervision_normal_count ?? 0,
    mirrorCount: prog.mirror_count ?? ctx.live_supervision_mirror_count ?? 0,
    calendarSessions: prog.calendar_sessions ?? 0,
    absences: prog.absences ?? 0,
    compensationPending: prog.compensation_pending ?? 0,
    compensationPaid: prog.compensation_paid ?? 0,
    compensationUrl: prog.compensation_payment_url || null,
    mirrorSessionIndex: ctx.mirror_session_index ?? prog.last_mirror_session_index ?? null,
    isComplete: (prog.normal_count ?? 0) >= NORMAL_REQUIRED && (prog.mirror_count ?? 0) >= MIRROR_REQUIRED,
  }
}

export function computeLiveSupervisionSla(ctx = {}, currentState, startedAt) {
  const cfg = SLA_CONFIG[currentState]
  if (!cfg) return null
  const merged = { ...ctx, started_at: startedAt }
  for (const key of cfg.keys) {
    if (merged[key]) {
      return { ...computeSlaRemaining(merged, cfg.days, key), title: cfg.title }
    }
  }
  if (startedAt) {
    return { ...computeSlaRemaining(merged, cfg.days, 'started_at'), title: cfg.title }
  }
  return { title: cfg.title, fallbackText: cfg.title }
}

export function LiveSupervisionSlaBanner({ ctx, currentState, startedAt }) {
  const sla = computeLiveSupervisionSla(ctx, currentState, startedAt)
  if (!sla) return null
  return <SlaBanner slaInfo={sla.expired != null ? sla : null} title={sla.title} fallbackText={sla.fallbackText} />
}

export function activeLiveSupervisionStepIndex(currentState) {
  if (!currentState) return 0
  if (isLiveSupervisionViolationState(currentState)) return LIVE_SUPERVISION_FLOW_STEPS.length - 1
  const idx = LIVE_SUPERVISION_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  if (idx >= 0) return idx
  if (currentState === 'completed') return LIVE_SUPERVISION_FLOW_STEPS.length - 1
  return 0
}

export function LiveSupervisionFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeLiveSupervisionStepIndex(currentState)
  const isViolation = isLiveSupervisionViolationState(currentState)

  return (
    <div
      data-testid="live-supervision-flow-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {LIVE_SUPERVISION_FLOW_STEPS.map((step, i) => {
        const done = i < activeIdx || currentState === 'completed'
        const active = i === activeIdx && !isViolation
        const tone = isViolation && i === activeIdx ? '#dc2626' : done ? '#16a34a' : active ? '#0d9488' : '#94a3b8'
        return (
          <div
            key={step.key}
            style={{
              flex: compact ? '1 1 30%' : '1 1 120px',
              padding: '0.45rem 0.6rem',
              borderRadius: '8px',
              border: `2px solid ${tone}`,
              background: active ? '#f0fdfa' : done ? '#f0fdf4' : '#f8fafc',
              fontSize: compact ? '0.72rem' : '0.8rem',
              fontWeight: active || done ? 700 : 500,
              color: tone,
              textAlign: 'center',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function progressBarLabel(normal, mirror) {
  return `${Number(normal).toLocaleString('fa-IR')} عادی + ${Number(mirror).toLocaleString('fa-IR')} پشت‌آینه (هدف: ۱۵+۳)`
}
