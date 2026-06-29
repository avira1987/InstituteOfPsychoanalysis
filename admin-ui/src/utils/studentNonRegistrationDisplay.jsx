/** نمایش مشترک فرایند ۴۲ — عدم ثبت‌نام دانشجو برای ترم بعد */

import React from 'react'
import { computeSlaRemaining } from './earlyTerminationChainDisplay'

export const NON_REG_MAX_WEEKS_FOR_REGISTER = 4
export const BRANCH_REGISTER_SLA_DAYS = 2
export const BRANCH_LEAVE_SLA_DAYS = 3

/** مراحل اصلی (milestone) فرایند ۴۲. */
export const NON_REG_FLOW_STEPS = [
  { key: 'identify', label: 'شناسایی', states: ['list_generated'] },
  { key: 'meeting', label: 'جلسه کمیته', states: ['meeting_scheduled', 'meeting_held'] },
  { key: 'decision', label: 'تصمیم و شاخه', states: ['branch_register', 'branch_leave', 'branch_withdrawal'] },
  { key: 'done', label: 'پایان', states: ['registration_completed', 'leave_started', 'withdrawal_triggered'] },
]

export const NON_REG_STATE_LABELS = {
  list_generated: 'لیست دانشجویان بدون ثبت‌نام',
  meeting_scheduled: 'جلسه تنظیم شده',
  meeting_held: 'جلسه برگزار شد — ثبت نتیجه',
  branch_register: 'قصد ثبت‌نام — مهلت ۲ روز',
  branch_leave: 'قصد مرخصی/وقفه — مهلت ۳ روز',
  branch_withdrawal: 'قصد انصراف',
  registration_completed: 'ثبت‌نام انجام شد',
  leave_started: 'فرایند مرخصی آغاز شد',
  withdrawal_triggered: 'انصراف از آموزش اجرا شد',
}

export const DECISION_LABELS = {
  register: 'قصد ثبت‌نام دارد',
  leave: 'قصد مرخصی/وقفه',
  withdrawal: 'قصد انصراف از تحصیل',
}

const TERMINAL_STATES = new Set([
  'branch_withdrawal',
  'registration_completed',
  'leave_started',
  'withdrawal_triggered',
])

export function labelNonRegState(state) {
  if (!state) return '—'
  return NON_REG_STATE_LABELS[state] || state
}

export function activeNonRegStepIndex(currentState) {
  if (!currentState) return 0
  if (TERMINAL_STATES.has(currentState)) return NON_REG_FLOW_STEPS.length - 1
  const idx = NON_REG_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function parseWeeks(raw) {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null
}

export function canChooseRegister(weeks) {
  const w = parseWeeks(weeks)
  if (w == null) return true
  return w <= NON_REG_MAX_WEEKS_FOR_REGISTER
}

export function weeksRegisterStatusFa(weeks) {
  const w = parseWeeks(weeks)
  if (w == null) return null
  if (w <= NON_REG_MAX_WEEKS_FOR_REGISTER) {
    return `مجاز برای ثبت‌نام دیرهنگام (${w.toLocaleString('fa-IR')} هفته از شروع کلاس‌ها)`
  }
  return `غیرمجاز — بیش از ${NON_REG_MAX_WEEKS_FOR_REGISTER.toLocaleString('fa-IR')} هفته از شروع کلاس‌ها گذشته (${w.toLocaleString('fa-IR')} هفته)`
}

export function resolveNonRegistrationContext(ctx = {}) {
  const weeks = parseWeeks(
    ctx.weeks_since_start ?? ctx.weeks_since_term_start,
  )
  return {
    termCode: ctx.term_code ? String(ctx.term_code) : null,
    weeksSinceStart: weeks,
    canRegister: canChooseRegister(weeks),
    decision: ctx.decision ?? ctx.non_registration_decision ?? null,
    meetingAt: ctx.committee_meeting_at ?? null,
    meetingMode: ctx.committee_meeting_mode ?? null,
    meetingLink: ctx.committee_meeting_link ?? null,
    meetingLocation: ctx.committee_meeting_location_fa ?? null,
    branchRegisterEnteredAt: ctx.branch_register_entered_at ?? null,
    branchRegisterDeadlineAt: ctx.branch_register_deadline_at ?? null,
    branchLeaveEnteredAt: ctx.branch_leave_entered_at ?? null,
    branchLeaveDeadlineAt: ctx.branch_leave_deadline_at ?? null,
  }
}

export function computeBranchSlaRemaining(ctx = {}, branch) {
  if (branch === 'register') {
    return computeSlaRemaining(ctx, BRANCH_REGISTER_SLA_DAYS, 'branch_register_entered_at')
      || computeSlaRemaining(ctx, BRANCH_REGISTER_SLA_DAYS, 'branch_register_deadline_at')
  }
  if (branch === 'leave') {
    return computeSlaRemaining(ctx, BRANCH_LEAVE_SLA_DAYS, 'branch_leave_entered_at')
      || computeSlaRemaining(ctx, BRANCH_LEAVE_SLA_DAYS, 'branch_leave_deadline_at')
  }
  return null
}

export function fmtMeetingDateTime(raw) {
  if (!raw || typeof raw !== 'string') return null
  const t = Date.parse(raw)
  if (Number.isNaN(t)) return raw
  try {
    return new Date(t).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return raw
  }
}

export function meetingModeLabel(mode) {
  if (mode === 'online') return 'آنلاین'
  if (mode === 'in_person') return 'حضوری'
  return ''
}

export function NonRegistrationFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeNonRegStepIndex(currentState)
  const completed = TERMINAL_STATES.has(currentState)

  return (
    <div
      data-testid="non-reg-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '0.45rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {NON_REG_FLOW_STEPS.map((step, i) => {
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
            {step.label}
          </div>
        )
      })}
    </div>
  )
}
