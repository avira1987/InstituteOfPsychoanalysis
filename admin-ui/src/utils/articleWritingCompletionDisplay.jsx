/** نمایش مشترک زنجیره «خاتمه درس مقاله‌نویسی» — فرایند ۶۹. */

import React from 'react'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { formatShamsiTehran } from './shamsiDateTime'

export const ARTICLE_WRITING_FLOW_STEPS = [
  {
    key: 'active',
    label: 'کلاس فعال',
    states: ['course_active'],
  },
  {
    key: 'defense_window',
    label: 'مهلت درخواست دفاع (۸ روز)',
    states: ['class_closed_student'],
  },
  {
    key: 'instructor_eval',
    label: 'ارزیابی مدرس (۴ روز)',
    states: ['instructor_eval_pending'],
  },
  {
    key: 'complete',
    label: 'انتقال به فاز دفاع',
    states: ['completed_to_defense'],
  },
]

export const ARTICLE_WRITING_STATE_LABELS = {
  course_active: 'کلاس مقاله‌نویسی فعال',
  class_closed_student: 'کلاس بسته — مهلت ۸ روزه درخواست دفاع',
  instructor_eval_pending: 'منتظر فرم ارزیابی مدرس (۴ روز)',
  completed_to_defense: 'خاتمه کلاس — انتقال به فاز دفاع',
  student_delay_violation: 'تأخیر دانشجو — گزارش تخلف',
  instructor_delay_violation: 'تأخیر مدرس — گزارش تخلف',
  term3_violation: 'اخذ ترم سوم — گزارش تخلف',
}

const VIOLATION_STATES = new Set([
  'student_delay_violation',
  'instructor_delay_violation',
  'term3_violation',
])

const SLA_CONFIG = {
  class_closed_student: {
    days: 8,
    keys: ['class_closed_at', 'completion_ticked_at', 'started_at'],
    title: 'مهلت ثبت درخواست دفاع (۸ روز)',
  },
  instructor_eval_pending: {
    days: 4,
    keys: ['defense_requested_at', 'instructor_eval_entered_at', 'class_closed_at'],
    title: 'مهلت تکمیل فرم ارزیابی مدرس (۴ روز)',
  },
}

export function labelArticleWritingState(state) {
  if (!state) return '—'
  return ARTICLE_WRITING_STATE_LABELS[state] || state
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function isArticleViolationState(state) {
  return VIOLATION_STATES.has(state)
}

export function resolveArticleContext(ctx = {}) {
  return {
    courseCode: ctx.course_code || ctx.course_id || '—',
    courseName: ctx.course_name || ctx.course_code || 'مقاله‌نویسی جهت گزارش موردی',
    enrollmentTerm: ctx.enrollment_term ?? ctx.article_enrollment_term ?? null,
    completionTickedAt: ctx.completion_ticked_at || null,
    classClosedAt: ctx.class_closed_at || null,
    defenseRequestedAt: ctx.defense_requested_at || null,
    studentName: ctx.student_name || null,
  }
}

export function resolveEvaluationSummary(ctx = {}) {
  const snapshot = ctx.performance_traits_snapshot
  if (Array.isArray(snapshot) && snapshot.length) {
    return snapshot
  }
  const out = []
  if (ctx.q7_has_positive === 'yes') {
    const traits = Array.isArray(ctx.q7_positive_traits) ? ctx.q7_positive_traits : []
    out.push({
      kind: 'positive',
      traits,
      trait_labels_fa: ctx.q7_positive_trait_labels || traits,
      note: ctx.q7_positive_note || null,
    })
  }
  if (ctx.q8_has_negative === 'yes') {
    const traits = Array.isArray(ctx.q8_negative_traits) ? ctx.q8_negative_traits : []
    out.push({
      kind: 'negative',
      traits,
      trait_labels_fa: ctx.q8_negative_trait_labels || traits,
      note: ctx.q8_negative_note || null,
    })
  }
  return out
}

export function computeArticleWritingSla(ctx = {}, currentState, startedAt) {
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

export function ArticleWritingSlaBanner({ ctx, currentState, startedAt }) {
  const sla = computeArticleWritingSla(ctx, currentState, startedAt)
  if (!sla) return null
  return <SlaBanner slaInfo={sla.expired != null ? sla : null} title={sla.title} fallbackText={sla.fallbackText} />
}

export function activeArticleWritingStepIndex(currentState) {
  if (!currentState) return 0
  if (isArticleViolationState(currentState)) return ARTICLE_WRITING_FLOW_STEPS.length - 1
  const idx = ARTICLE_WRITING_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  if (idx >= 0) return idx
  if (currentState === 'completed_to_defense') return ARTICLE_WRITING_FLOW_STEPS.length - 1
  return 0
}

export function ArticleWritingFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeArticleWritingStepIndex(currentState)
  const isViolation = isArticleViolationState(currentState)

  return (
    <div
      data-testid="article-writing-flow-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {ARTICLE_WRITING_FLOW_STEPS.map((step, i) => {
        const done = i < activeIdx || (currentState === 'completed_to_defense' && i <= activeIdx)
        const active = i === activeIdx && !isViolation
        const tone = isViolation && i === activeIdx ? '#dc2626' : done ? '#16a34a' : active ? '#2563eb' : '#94a3b8'
        return (
          <div
            key={step.key}
            style={{
              flex: compact ? '1 1 45%' : '1 1 140px',
              padding: '0.45rem 0.6rem',
              borderRadius: '8px',
              border: `2px solid ${tone}`,
              background: active ? '#eff6ff' : done ? '#f0fdf4' : '#f8fafc',
              fontSize: compact ? '0.75rem' : '0.82rem',
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

export function HintBlock({ tone = 'info', children }) {
  const styles = {
    info: { bg: '#eff6ff', border: '#2563eb', color: '#1e3a8a' },
    warn: { bg: '#fffbeb', border: '#d97706', color: '#92400e' },
    success: { bg: '#f0fdf4', border: '#16a34a', color: '#166534' },
    danger: { bg: '#fef2f2', border: '#dc2626', color: '#991b1b' },
  }[tone] || { bg: '#eff6ff', border: '#2563eb', color: '#1e3a8a' }

  return (
    <div
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: styles.bg,
        borderRight: `4px solid ${styles.border}`,
        fontSize: '0.86rem',
        lineHeight: 1.75,
        color: styles.color,
      }}
    >
      {children}
    </div>
  )
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

export function EvaluationSummaryBlock({ summary = [] }) {
  if (!summary.length) return null
  return (
    <div
      data-testid="article-evaluation-summary"
      style={{
        marginTop: '0.75rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: '0.5rem', fontSize: '0.88rem' }}>خلاصه ارزیابی ثبت‌شده</div>
      {summary.map((row, i) => (
        <div key={i} style={{ marginBottom: '0.5rem', fontSize: '0.85rem', lineHeight: 1.7 }}>
          <strong>{row.kind === 'positive' ? 'ویژگی‌های مثبت' : 'ویژگی‌های منفی'}:</strong>
          {' '}
          {(row.trait_labels_fa || row.traits || []).join('، ') || '—'}
          {row.note && (
            <div style={{ color: '#64748b', marginTop: '0.2rem' }}>{row.note}</div>
          )}
        </div>
      ))}
    </div>
  )
}
