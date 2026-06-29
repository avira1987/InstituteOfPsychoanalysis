/** نمایش مشترک فرایند ۵۶ — کنسل جلسات کلاس‌های درسی. */

import React from 'react'
import { fmtIsoDate } from './lessonStartPerTermDisplay'
import { resolveStateDisplayLabel } from './processDisplay'

export const PROCESS_CODE = 'class_session_cancellation'

export const PROCESS_TITLE_FA = 'کنسل جلسات کلاس‌های درسی (فرایند ۵۶)'

export const FLOW_STEPS = [
  { key: 'lesson', label: 'انتخاب درس', states: ['cancellation_request'] },
  { key: 'session', label: 'انتخاب جلسه', states: ['cancellation_request'] },
  { key: 'makeup', label: 'تأیید جبرانی', states: ['cancellation_request'] },
  { key: 'done', label: 'اعمال شد', states: ['makeup_scheduled'] },
]

export const STATE_LABELS = {
  cancellation_request: 'انتخاب درس و جلسه جهت کنسلی',
  makeup_scheduled: 'زمان جبرانی محاسبه و تأیید شد',
}

export const STATE_HINTS = {
  cancellation_request:
    'درس و جلسهٔ کنسل‌شونده را در فرم انتخاب کنید. زمان جبرانی به‌صورت خودکار در جمعه‌های هفته ۱۵ یا ۱۶ محاسبه می‌شود. کنسلی بدون تأیید هم‌زمان جبرانی ممکن نیست.',
  makeup_scheduled:
    'کنسلی ثبت شد. حضور و غیاب جلسهٔ اصلی قفل شده و جلسهٔ جبرانی در تقویم کلاس اضافه شده است. پس از برگزاری، حضور را در ستون جلسهٔ جبرانی ثبت کنید.',
}

const ORDINAL_FA = {
  1: 'اول',
  2: 'دوم',
  3: 'سوم',
  4: 'چهارم',
}

export function labelClassCancellationState(state, processCode = PROCESS_CODE) {
  if (!state) return '—'
  return STATE_LABELS[state] || resolveStateDisplayLabel(state, null, processCode)
}

export function activeCancellationStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'makeup_scheduled') return FLOW_STEPS.length - 1
  return 0
}

export function resolveClassCancellationContext(ctx = {}, stepFormValues = {}) {
  const merged = { ...ctx, ...stepFormValues }
  const lessonId = merged.lesson_id || merged.course_code || ''
  const sessionKey = merged.session_to_cancel || ''
  const sessions = Array.isArray(merged.upcoming_cancellable_sessions)
    ? merged.upcoming_cancellable_sessions
    : []
  const cancellable = Array.isArray(merged.cancellable_sessions)
    ? merged.cancellable_sessions
    : sessions.filter((s) => s?.cancellable !== false)

  let selectedSession = merged.selected_session_detail || null
  if (!selectedSession && sessionKey) {
    selectedSession = sessions.find((s) => s.value === sessionKey) || null
  }

  const ordinal = merged.cancellation_ordinal != null
    ? Number(merged.cancellation_ordinal)
    : null
  const ordinalFa = merged.cancellation_ordinal_fa
    || (ordinal != null ? ORDINAL_FA[ordinal] || String(ordinal) : null)

  return {
    lessonId,
    lessonLabel: lessonId || '—',
    sessionKey,
    selectedSession,
    sessions,
    cancellable,
    courses: Array.isArray(merged.assignable_courses) ? merged.assignable_courses : [],
    makeupDate: merged.makeup_date || '',
    makeupTime: merged.makeup_time || '',
    makeupSummary: merged.makeup_summary_fa || '',
    termWeekLabel: merged.term_week_makeup_label || '',
    ordinal,
    ordinalFa,
    usualTime: merged.usual_class_time || '',
    violationPending: Boolean(merged.violation_pending),
    violationHint: merged.violation_hint_fa || '',
    cancelledSession: merged.cancelled_session || null,
    makeupSession: merged.makeup_session || null,
    studentsUpdated: merged.students_updated != null ? Number(merged.students_updated) : null,
  }
}

export function CancellationStatTile({ label, value, sub, accent }) {
  if (value == null || value === '') return null
  return (
    <div
      style={{
        padding: '0.85rem',
        borderRadius: '10px',
        background: accent?.bg || '#f8fafc',
        borderRight: `4px solid ${accent?.color || '#94a3b8'}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{label}</div>
      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: accent?.color || '#0f172a' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '0.78rem', color: '#78716c', marginTop: '0.25rem' }}>{sub}</div>
      )}
    </div>
  )
}

export function ClassCancellationFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeCancellationStepIndex(currentState)
  const terminal = currentState === 'makeup_scheduled'

  return (
    <div
      data-testid="class-cancellation-flow-stepper"
      style={{
        display: 'flex',
        gap: compact ? '0.25rem' : '0.35rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
        flexWrap: 'wrap',
      }}
    >
      {FLOW_STEPS.map((step, i) => {
        const done = terminal ? i <= activeIdx : i < activeIdx
        const active = !terminal && i === activeIdx
        const terminalHere = terminal && i === activeIdx
        return (
          <div
            key={step.key}
            style={{
              flex: '1 1 5rem',
              padding: compact ? '0.35rem 0.45rem' : '0.45rem 0.55rem',
              borderRadius: '8px',
              background: terminalHere ? '#ccfbf1' : active ? '#0d9488' : done ? '#ccfbf1' : '#f1f5f9',
              color: terminalHere ? '#115e59' : active ? '#fff' : done ? '#115e59' : '#64748b',
              border: active ? '2px solid #0f766e' : '1px solid #e2e8f0',
              fontSize: compact ? '0.68rem' : '0.72rem',
              textAlign: 'center',
              fontWeight: active || terminalHere ? 700 : 500,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function ClassCancellationHintBlock({ children, tone = 'info' }) {
  const styles = {
    info: { bg: '#eff6ff', border: '#2563eb', color: '#1e3a8a' },
    warn: { bg: '#fffbeb', border: '#d97706', color: '#92400e' },
    success: { bg: '#f0fdf4', border: '#16a34a', color: '#166534' },
  }[tone] || { bg: '#eff6ff', border: '#2563eb', color: '#1e3a8a' }

  return (
    <div
      data-testid="class-cancellation-hint"
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

export function MakeupPreviewBlock({ makeupDate, makeupTime, summary, termWeekLabel, ordinalFa }) {
  if (!makeupDate && !makeupTime) return null
  return (
    <div
      data-testid="class-cancellation-makeup-preview"
      style={{
        marginBottom: '0.85rem',
        padding: '0.85rem 1rem',
        borderRadius: '10px',
        background: '#f0fdfa',
        border: '1px solid #99f6e4',
        borderRight: '4px solid #0d9488',
      }}
    >
      <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#115e59', marginBottom: '0.35rem' }}>
        پیش‌نمایش کلاس جبرانی
        {ordinalFa ? ` (کنسلی ${ordinalFa})` : ''}
        {termWeekLabel ? ` — ${termWeekLabel}` : ''}
      </div>
      <div style={{ fontSize: '1rem', fontWeight: 800, color: '#0f766e' }}>
        {fmtIsoDate(makeupDate)}
        {makeupTime ? ` — ساعت ${makeupTime}` : ''}
      </div>
      {summary && (
        <div style={{ fontSize: '0.8rem', color: '#334155', marginTop: '0.35rem' }}>{summary}</div>
      )}
    </div>
  )
}

export function SessionPickList({ sessions, selectedKey, compact = false }) {
  if (!sessions?.length) return null
  return (
    <div
      data-testid="class-cancellation-session-list"
      style={{ marginBottom: '0.85rem' }}
    >
      <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.45rem' }}>
        جلسات درس
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        {sessions.map((s) => {
          const selected = s.value === selectedKey
          const cancellable = s.cancellable !== false
          return (
            <div
              key={s.value || s.session_key}
              style={{
                padding: compact ? '0.45rem 0.65rem' : '0.55rem 0.75rem',
                borderRadius: '8px',
                border: selected ? '2px solid #0d9488' : '1px solid #e2e8f0',
                background: selected ? '#f0fdfa' : cancellable ? '#fff' : '#f8fafc',
                fontSize: '0.82rem',
                display: 'flex',
                justifyContent: 'space-between',
                gap: '0.5rem',
                flexWrap: 'wrap',
              }}
            >
              <span>{s.label_fa || s.value}</span>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: cancellable ? '#166534' : '#64748b',
                }}
              >
                {s.status_fa || (cancellable ? 'قابل کنسلی' : '—')}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
