/** نمایش مشترک فرایند ۵۵ — ثبت تخلفات */

import React from 'react'
import { computeSlaRemaining } from './earlyTerminationChainDisplay'

export const FIRST_ACTION_SLA_DAYS = 3
export const COMPENSATORY_SLA_DAYS = 7

export const VIOLATION_FLOW_STEPS = [
  { key: 'report', label: 'ثبت و غربالگری', states: ['violation_reported'] },
  { key: 'review', label: 'بررسی و جلسه', states: ['review_status_set', 'meeting_scheduled'] },
  { key: 'verdict', label: 'حکم', states: ['verdict_issued'] },
  { key: 'advanced', label: 'تعلیق/ارجاع', states: ['suspension_next_term', 'suspension_immediate', 'referred_to_education_committee'] },
  { key: 'done', label: 'پایان', states: ['closed', 'expelled'] },
]

export const VIOLATION_STATE_LABELS = {
  violation_reported: 'تخلف ثبت و ارجاع به کمیته نظارت',
  review_status_set: 'تعیین نوع تخلف و جلسه',
  meeting_scheduled: 'جلسه تنظیم شد',
  verdict_issued: 'حکم صادر شد',
  suspension_next_term: 'تعلیق از ترم بعد',
  suspension_immediate: 'تعلیق آنی',
  referred_to_education_committee: 'ارجاع به کمیته آموزش',
  closed: 'مختومه',
  expelled: 'اخراج — پورتال مسدود',
}

export const VIOLATION_TYPE_LABELS = {
  professional: 'حرفه‌ای',
  educational: 'آموزشی',
  disciplinary: 'انضباطی',
}

export const VERDICT_LABELS = {
  cleared: 'مبرا',
  notice: 'تذکر',
  warning_1: 'اخطار مرحله اول',
  warning_2: 'اخطار مرحله دوم',
  warning_3: 'اخطار مرحله سوم',
  suspension_next_term: 'تعلیق از ترم بعد',
  suspension_immediate: 'تعلیق آنی',
  refer_education: 'ارجاع به کمیته آموزش',
  no_expulsion: 'عدم اخراج',
  expulsion: 'اخراج از آموزش',
}

const TERMINAL_STATES = new Set(['closed', 'expelled'])

export function labelViolationState(state) {
  if (!state) return '—'
  return VIOLATION_STATE_LABELS[state] || state
}

export function labelViolationType(raw) {
  if (!raw) return '—'
  return VIOLATION_TYPE_LABELS[raw] || raw
}

export function labelVerdict(raw) {
  if (!raw) return '—'
  return VERDICT_LABELS[raw] || raw
}

export function activeViolationStepIndex(currentState) {
  if (!currentState) return 0
  if (TERMINAL_STATES.has(currentState)) return VIOLATION_FLOW_STEPS.length - 1
  const idx = VIOLATION_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function meetingModeLabel(mode) {
  if (mode === 'online') return 'آنلاین'
  if (mode === 'in_person') return 'حضوری'
  return mode || '—'
}

export function fmtMeetingDateTime(raw) {
  if (!raw) return null
  try {
    const d = new Date(raw)
    if (Number.isNaN(d.getTime())) return String(raw)
    return d.toLocaleString('fa-IR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return String(raw)
  }
}

export function resolveViolationContext(ctx = {}, stepFormValues = {}) {
  const merged = { ...ctx, ...stepFormValues }
  const verdict = merged.verdict || merged.verdict_action
  return {
    sourceReason: merged.source_reason || merged.reason || null,
    sourceProcessCode: merged.source_process_code || null,
    parentInstanceId: merged.parent_instance_id || null,
    description: (merged.description || merged.title_fa || '').trim() || null,
    occurrenceDate: merged.occurrence_date || null,
    violationType: merged.violation_type || null,
    violationTypeLabel: labelViolationType(merged.violation_type),
    reviewable: merged.reviewable || null,
    needsMeeting: merged.needs_meeting || null,
    meetingAt: merged.meeting_at || null,
    meetingMode: merged.meeting_mode || null,
    meetingLink: (merged.meeting_link || '').trim() || null,
    meetingLocation: (merged.meeting_location_fa || '').trim() || null,
    verdict,
    verdictLabel: labelVerdict(verdict) || merged.verdict_action || null,
    compensatoryConditions: (merged.compensatory_conditions || '').trim() || null,
    finalDecision: merged.final_decision || null,
    finalDecisionLabel: labelVerdict(merged.final_decision),
    educationMeetingAt: merged.education_meeting_at || null,
    educationMeetingLink: (merged.education_meeting_link || '').trim() || null,
    reportedAt: merged.violation_reported_at || merged.started_at || null,
  }
}

export function computeFirstActionSlaRemaining(ctx) {
  return computeSlaRemaining(
    ctx,
    FIRST_ACTION_SLA_DAYS,
    'violation_reported_at',
  ) || computeSlaRemaining(ctx, FIRST_ACTION_SLA_DAYS, 'started_at')
}

export function computeCompensatorySlaRemaining(ctx) {
  return computeSlaRemaining(
    ctx,
    COMPENSATORY_SLA_DAYS,
    'last_performance_entry_at',
  ) || computeSlaRemaining(ctx, COMPENSATORY_SLA_DAYS, 'verdict_issued_at')
}

export function ViolationFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeViolationStepIndex(currentState)
  return (
    <div
      data-testid="violation-flow-stepper"
      style={{
        display: 'flex',
        gap: compact ? '0.25rem' : '0.35rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
        flexWrap: 'wrap',
      }}
    >
      {VIOLATION_FLOW_STEPS.map((step, i) => {
        const done = i < activeIdx
        const active = i === activeIdx
        return (
          <div
            key={step.key}
            style={{
              flex: '1 1 6rem',
              padding: compact ? '0.35rem 0.45rem' : '0.45rem 0.55rem',
              borderRadius: '8px',
              background: active ? '#b91c1c' : done ? '#fee2e2' : '#f1f5f9',
              color: active ? '#fff' : done ? '#991b1b' : '#64748b',
              border: active ? '2px solid #991b1b' : '1px solid #e2e8f0',
              fontSize: compact ? '0.68rem' : '0.72rem',
              textAlign: 'center',
              fontWeight: active ? 700 : 500,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

function fmtLogDate(raw) {
  if (!raw) return '—'
  try {
    const d = new Date(raw)
    if (Number.isNaN(d.getTime())) return String(raw)
    return d.toLocaleDateString('fa-IR')
  } catch {
    return String(raw)
  }
}

/**
 * جدول گزارش عملکرد دانشجو (کمیته نظارت) — از extra_data یا آرگومان.
 */
export function StudentPerformanceLogTable({
  log = [],
  title = 'گزارش عملکرد دانشجو (کمیته نظارت)',
  compact = false,
  testId = 'student-performance-log-table',
}) {
  const rows = Array.isArray(log) ? [...log].reverse() : []
  if (!rows.length) {
    return (
      <div
        data-testid={testId}
        style={{
          padding: '0.75rem 1rem',
          borderRadius: '10px',
          background: '#f8fafc',
          fontSize: '0.84rem',
          color: '#64748b',
        }}
      >
        <strong style={{ display: 'block', marginBottom: '0.35rem', color: '#334155' }}>{title}</strong>
        هنوز رکوردی ثبت نشده است.
      </div>
    )
  }

  return (
    <div data-testid={testId} style={{ marginTop: compact ? '0.5rem' : '0.75rem' }}>
      <strong style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.88rem' }}>{title}</strong>
      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: compact ? '0.76rem' : '0.82rem',
          }}
        >
          <thead>
            <tr style={{ background: '#f1f5f9', textAlign: 'right' }}>
              <th style={{ padding: '0.45rem 0.55rem', borderBottom: '1px solid #e2e8f0' }}>تاریخ</th>
              <th style={{ padding: '0.45rem 0.55rem', borderBottom: '1px solid #e2e8f0' }}>گزارش‌دهنده</th>
              <th style={{ padding: '0.45rem 0.55rem', borderBottom: '1px solid #e2e8f0' }}>شرح / نوع</th>
              <th style={{ padding: '0.45rem 0.55rem', borderBottom: '1px solid #e2e8f0' }}>حکم</th>
              <th style={{ padding: '0.45rem 0.55rem', borderBottom: '1px solid #e2e8f0' }}>شروط جبرانی</th>
              <th style={{ padding: '0.45rem 0.55rem', borderBottom: '1px solid #e2e8f0' }}>وضعیت نهایی</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              const kind = row.kind || 'violation'
              const desc = kind === 'violation'
                ? (row.description || row.violation_type_fa || labelViolationType(row.violation_type))
                : (row.trait_labels_fa || []).join('، ') || row.note || kind
              const verdict = row.verdict_action_fa || labelVerdict(row.verdict_action) || '—'
              const reporter = row.reporter_name || '—'
              return (
                <tr key={row.at || idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '0.45rem 0.55rem' }}>{fmtLogDate(row.at)}</td>
                  <td style={{ padding: '0.45rem 0.55rem' }}>{reporter}</td>
                  <td style={{ padding: '0.45rem 0.55rem', maxWidth: '14rem' }}>{desc || '—'}</td>
                  <td style={{ padding: '0.45rem 0.55rem' }}>{verdict}</td>
                  <td style={{ padding: '0.45rem 0.55rem', maxWidth: '12rem' }}>
                    {row.compensatory_conditions || '—'}
                  </td>
                  <td style={{ padding: '0.45rem 0.55rem' }}>
                    {row.final_status_fa || labelVerdict(row.final_status) || '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
