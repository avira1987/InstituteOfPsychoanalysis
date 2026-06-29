/** نمایش مشترک فرایند ۴۹ — ارتقا به دستیار هیئت علمی. */

import React from 'react'
import { HintBlock, InfoTile } from './upgradeToEducationalTherapistDisplay'

export { HintBlock, InfoTile }

export const TA_ASSISTANT_FLOW_STEPS = [
  { key: 'trigger', label: 'احراز و آغاز', states: ['auto_or_manual_trigger'] },
  { key: 'review', label: 'کمیته نظارت', states: ['supervision_review'] },
  {
    key: 'outcome',
    label: 'نتیجه',
    states: ['already_assistant', 'supervision_rejected', 'upgrade_applied'],
  },
]

export const TA_ASSISTANT_STOP_STATES = new Set([
  'already_assistant',
  'supervision_rejected',
  'upgrade_applied',
])

export const TA_ASSISTANT_STOP_MESSAGES = {
  already_assistant:
    'شما قبلاً رتبهٔ تحلیلی دستیار هیئت علمی را اخذ کرده‌اید.',
  supervision_rejected:
    'صلاحیت ارتقا توسط کمیته نظارت تأیید نشد. می‌توانید در ترم‌های بعد درخواست ارزیابی مجدد ثبت کنید.',
  upgrade_applied:
    'ارتقا با موفقیت اعمال شد. نقش شما در این درس به مدرس تغییر یافت و در صورت اولین ارتقا، رتبهٔ تحلیلی به دستیار هیئت علمی ارتقا یافت.',
}

export const TA_ASSISTANT_STATE_HINTS = {
  auto_or_manual_trigger: 'درخواست ارتقا در حال پردازش سیستمی است.',
  supervision_review: 'پرونده در کمیته نظارت در حال بررسی است.',
  already_assistant: TA_ASSISTANT_STOP_MESSAGES.already_assistant,
  supervision_rejected: TA_ASSISTANT_STOP_MESSAGES.supervision_rejected,
  upgrade_applied: TA_ASSISTANT_STOP_MESSAGES.upgrade_applied,
}

export const TA_ASSISTANT_COMMITTEE_HINTS = {
  supervision_review:
    'پروندهٔ ارتقای آموزشی را بررسی کنید. فرم تصمیم را تکمیل کنید، سپس «تایید» یا «رد» را بزنید. '
    + 'اگر متقاضی قبلاً دستیار هیئت علمی است، فقط صلاحیت تدریس این درس بررسی می‌شود.',
}

export const RANK_LABELS = {
  teaching_assistant: 'کمک‌مدرس',
  assistant_faculty: 'دستیار هیئت علمی',
  instructor: 'مدرس',
}

export function isTaAssistantStopState(state) {
  return TA_ASSISTANT_STOP_STATES.has(state)
}

export function resolveTaUpgradeContext(ctx = {}) {
  const passCount = Number(ctx.ta_pass_count ?? 0)
  const required = Number(ctx.required_passes ?? 2)
  return {
    courseCode: ctx.course_code || '—',
    courseName: ctx.course_name_fa || ctx.course_name || '—',
    passCount,
    requiredPasses: required,
    passSummary: passCount >= required
      ? `${passCount} بار موفق (تأیید سیستمی)`
      : `${passCount}/${required}`,
    currentRankFa: ctx.current_analytic_rank_fa || RANK_LABELS[ctx.current_rank] || ctx.current_rank || '—',
    alreadyAssistant: ctx.already_assistant_faculty === true,
    summaryFa: ctx.ta_upgrade_summary_fa || '—',
    portalMessageFa: ctx.student_portal_message_fa || null,
    manualRetryAvailable: ctx.manual_retry_available === true,
    studentName: ctx.student_name_fa || ctx.student_code_display || '—',
  }
}

export function TaAssistantFlowStepper({ currentState }) {
  const activeIdx = TA_ASSISTANT_FLOW_STEPS.findIndex((step) =>
    step.states.includes(currentState),
  )
  const idx = activeIdx >= 0 ? activeIdx : 0

  return (
    <div
      data-testid="ta-assistant-upgrade-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '0.5rem',
        marginBottom: '1rem',
      }}
    >
      {TA_ASSISTANT_FLOW_STEPS.map((step, i) => {
        const done = i < idx || currentState === 'upgrade_applied'
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
              background: done ? '#f0fdf4' : active ? '#fffbeb' : '#f8fafc',
              borderRight: `3px solid ${done ? '#16a34a' : active ? '#d97706' : '#e2e8f0'}`,
              color: done ? '#166534' : active ? '#92400e' : '#64748b',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}
